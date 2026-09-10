"""
Server-side Risk Gate for AUREXIS.

Authoritative decision engine for Phase 3 market data and risk validation.
Evaluates agent state, market-data freshness, price sanity, account equity,
and risk boundaries.

ABSOLUTE RULE:
Produces ONLY deterministic ALLOW or BLOCK decisions.
NEVER places orders, executes trades, or creates BUY/SELL commands.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.core.logging import get_logger
from backend.db.models.account import TradingAccount
from backend.db.models.mt5_agent import MT5Agent
from backend.services import market_data_service
from backend.services.risk_service import (
    build_account_risk_snapshot,
    get_latest_risk_config,
)
from backend.ws.agent_manager import agent_manager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("risk.gate")

CANONICAL_SYMBOL = "XAUUSD"


class RiskDecisionOutput:
    """Structured deterministic risk decision representation."""

    def __init__(
        self,
        decision: str,
        reason_code: str,
        reason: str,
        symbol: str = CANONICAL_SYMBOL,
        market_data: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.decision = decision
        self.reason_code = reason_code
        self.reason = reason
        self.symbol = symbol
        self.timestamp = datetime.now(UTC).isoformat()
        self.market_data = market_data
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "market_data": self.market_data,
            "details": self.details,
        }


async def evaluate_risk_gate(
    session: AsyncSession,
    account_id: uuid.UUID,
    symbol: str = CANONICAL_SYMBOL,
    *,
    override_tick: dict[str, Any] | None = None,
    override_agent_connected: bool | None = None,
) -> RiskDecisionOutput:
    """
    Authoritative server-side risk evaluation. Produces strictly ALLOW or BLOCK.
    """
    norm_symbol = market_data_service.normalize_symbol(symbol)
    config = await get_latest_risk_config(session, account_id)

    # 1. Emergency kill switch check
    if config.emergency_stop_active:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="KILL_SWITCH_ACTIVE",
            reason="Emergency kill switch is active.",
            symbol=norm_symbol,
        )

    # 2. Symbol validity check
    if norm_symbol != CANONICAL_SYMBOL:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="INVALID_SYMBOL",
            reason=f"Symbol '{symbol}' is not supported. Only XAUUSD is permitted.",
            symbol=symbol,
        )

    # 3. Agent connection check
    agent_res = await session.execute(
        select(MT5Agent).where(
            MT5Agent.account_id == account_id,
        ).limit(1)
    )
    agent = agent_res.scalar_one_or_none()
    if agent is None:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="AGENT_OFFLINE",
            reason="No active MT5 agent configured for this account.",
            symbol=norm_symbol,
        )

    is_conn = (
        override_agent_connected
        if override_agent_connected is not None
        else agent_manager.is_connected(str(agent.id))
    )
    if not is_conn:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="AGENT_OFFLINE",
            reason="MT5 execution agent is currently disconnected.",
            symbol=norm_symbol,
        )

    # 4. Market data presence & freshness check
    tick = (
        override_tick
        if override_tick is not None
        else await market_data_service.get_latest_market_data(account_id, norm_symbol)
    )
    if not tick:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="MARKET_DATA_NOT_READY",
            reason="No market data tick received yet for symbol.",
            symbol=norm_symbol,
        )

    max_staleness_ms = config.max_tick_staleness_ms or 2000
    is_fresh, _, age_ms = market_data_service.evaluate_freshness(
        tick, max_staleness_ms=max_staleness_ms
    )
    if not is_fresh:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="MARKET_DATA_STALE",
            reason=f"Market data tick is stale ({age_ms}ms > {max_staleness_ms}ms).",
            symbol=norm_symbol,
            market_data=tick,
            details={"age_ms": age_ms, "max_staleness_ms": max_staleness_ms},
        )

    # 5. Price & spread sanity check
    try:
        bid = Decimal(str(tick["bid"]))
        ask = Decimal(str(tick["ask"]))
        spread = Decimal(str(tick["spread"]))
    except Exception as exc:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="INVALID_SPREAD",
            reason=f"Malformed numeric price or spread values: {exc}",
            symbol=norm_symbol,
            market_data=tick,
        )

    if bid <= Decimal("0"):
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="INVALID_BID",
            reason=f"Bid price must be positive ({bid}).",
            symbol=norm_symbol,
            market_data=tick,
        )
    if ask <= bid:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="INVALID_ASK",
            reason=f"Ask price ({ask}) cannot be less than or equal to bid ({bid}).",
            symbol=norm_symbol,
            market_data=tick,
        )
    if spread < Decimal("0"):
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="INVALID_SPREAD",
            reason=f"Spread cannot be negative ({spread}).",
            symbol=norm_symbol,
            market_data=tick,
        )
    if config.max_spread_usd is not None and spread > config.max_spread_usd:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="INVALID_SPREAD",
            reason=f"Spread ({spread}) exceeds max allowable limit ({config.max_spread_usd}).",
            symbol=norm_symbol,
            market_data=tick,
            details={"spread": str(spread), "max_spread_usd": str(config.max_spread_usd)},
        )

    # 6. Account equity check
    acct_res = await session.execute(
        select(TradingAccount).where(
            TradingAccount.id == account_id,
            TradingAccount.is_active.is_(True),
        )
    )
    account = acct_res.scalar_one_or_none()
    if account is None:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="ACCOUNT_STATE_UNAVAILABLE",
            reason="Trading account not found or inactive.",
            symbol=norm_symbol,
            market_data=tick,
        )

    snapshot = await build_account_risk_snapshot(session, account_id)
    if snapshot.current_equity_usd <= Decimal("0"):
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="ACCOUNT_STATE_UNAVAILABLE",
            reason="Account equity is zero or negative.",
            symbol=norm_symbol,
            market_data=tick,
            details={"equity_usd": str(snapshot.current_equity_usd)},
        )

    # 7. Configured risk boundary checks (daily loss & max drawdown)
    total_daily_pnl = snapshot.daily_realized_pnl_usd + snapshot.daily_floating_pnl_usd
    if config.daily_loss_limit_usd is not None and total_daily_pnl <= -config.daily_loss_limit_usd:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="RISK_LIMIT_BLOCK",
            reason=f"Daily loss limit breached: {total_daily_pnl} <= -{config.daily_loss_limit_usd}",
            symbol=norm_symbol,
            market_data=tick,
            details={"daily_pnl_usd": str(total_daily_pnl), "limit": str(config.daily_loss_limit_usd)},
        )

    drawdown = snapshot.equity_peak_usd - snapshot.current_equity_usd
    if config.max_drawdown_usd is not None and drawdown >= config.max_drawdown_usd:
        return RiskDecisionOutput(
            decision="BLOCK",
            reason_code="RISK_LIMIT_BLOCK",
            reason=f"Max drawdown breached: {drawdown} >= {config.max_drawdown_usd}",
            symbol=norm_symbol,
            market_data=tick,
            details={"drawdown_usd": str(drawdown), "limit": str(config.max_drawdown_usd)},
        )

    # 8. All checks passed
    return RiskDecisionOutput(
        decision="ALLOW",
        reason_code="RISK_OK",
        reason="All Phase 3 risk checks passed: market data, agent connection, and account risk parameters verified.",
        symbol=norm_symbol,
        market_data=tick,
        details={
            "age_ms": age_ms,
            "bid": str(bid),
            "ask": str(ask),
            "spread": str(spread),
            "equity_usd": str(snapshot.current_equity_usd),
        },
    )

