"""
Risk Engine — core evaluation logic.

The Risk Engine receives account state, candidate signal, market condition, and configuration.
It returns a deterministic decision: APPROVED, BLOCKED, NOT_CONFIGURED, or EMERGENCY.

CRITICAL RULES:
1. If required configuration is missing -> NOT_CONFIGURED (no trade).
2. If emergency stop is active -> EMERGENCY (no trade).
3. If market data is stale or degraded -> BLOCKED (fail-closed).
4. If news blackout is active or news unavailable -> BLOCKED (fail-closed).
5. If daily loss limit hit -> BLOCKED.
6. If max drawdown hit -> BLOCKED.
7. If profit lock floor breached -> BLOCKED.
8. If max positions or max lots reached -> BLOCKED.
9. Fail safe: when uncertain -> DO NOT OPEN NEW TRADE.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.risk.sizing import (
    FixedLotSizingPolicy,
    PercentageEquitySizingPolicy,
    PositionSizingPolicy,
)
from backend.risk.states import RiskState, SignalDecision

if TYPE_CHECKING:
    from backend.risk.config import RiskConfig

logger = get_logger("risk.engine")


@dataclass(frozen=True)
class AccountRiskSnapshot:
    """
    Current financial state of a trading account, normalized to USD.
    All values are in USD (after cent normalization).
    equity_peak_usd is the LIFETIME high-water mark — never reset per session.
    """
    account_id: str
    current_balance_usd: Decimal
    current_equity_usd: Decimal
    equity_peak_usd: Decimal
    daily_realized_pnl_usd: Decimal
    daily_floating_pnl_usd: Decimal
    open_position_count: int
    snapshot_at: datetime
    session_open_equity_usd: Decimal | None = None
    session_peak_profit_usd: Decimal | None = None
    open_lot_exposure: Decimal = Decimal("0")
    in_flight_lot_exposure: Decimal = Decimal("0")


@dataclass(frozen=True)
class MarketCondition:
    """Real-time market pricing and staleness context."""
    symbol: str = "XAUUSD"
    bid: Decimal | None = None
    ask: Decimal | None = None
    tick_timestamp: datetime | None = None
    tick_age_ms: int | None = None
    spread: Decimal | None = None
    market_data_status: str = "READY"

    @property
    def effective_spread(self) -> Decimal | None:
        if self.spread is not None:
            return self.spread
        if self.ask is not None and self.bid is not None:
            return self.ask - self.bid
        return None


@dataclass(frozen=True)
class ProfitLockStatus:
    """Profit-lock evaluation result. LOCKED: PCT_RETRACE, FLOATING_EQUITY basis."""
    is_active: bool
    session_profit_usd: Decimal
    peak_profit_usd: Decimal
    protected_floor_usd: Decimal
    is_breached: bool

@dataclass(frozen=True)
class RiskDecision:
    """
    Deterministic output from the Risk Engine.
    APPROVED is the only state that permits new entry commands.
    """
    decision: SignalDecision
    reason_code: str
    risk_state: RiskState
    account_id: str
    correlation_id: str
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    equity_at_decision: Decimal | None = None
    drawdown_at_decision: Decimal | None = None
    daily_pnl_at_decision: Decimal | None = None
    profit_lock_status: ProfitLockStatus | None = None
    authorized_lot_size: Decimal | None = None

    @property
    def trading_allowed(self) -> bool:
        return self.decision == SignalDecision.APPROVED


class RiskEngine:
    """
    AUREXIS Risk Engine — deterministic state machine.

    Evaluates whether a new trade entry is permitted given current
    account state, market conditions, and risk configuration. Fail-safe.
    """

    def __init__(self, config: RiskConfig, sizing_policy: PositionSizingPolicy | None = None) -> None:
        self._config = config
        self._sizing_policy = sizing_policy

    def _get_sizing_policy(self) -> PositionSizingPolicy | None:
        if self._sizing_policy is not None:
            return self._sizing_policy
        if self._config.risk_per_trade_pct is not None:
            return PercentageEquitySizingPolicy(risk_per_trade_pct=self._config.risk_per_trade_pct)
        if self._config.default_position_size_lots is not None:
            return FixedLotSizingPolicy(fixed_lots=self._config.default_position_size_lots)
        return None

    def evaluate(
        self,
        snapshot: AccountRiskSnapshot,
        candidate_signal: Any | None = None,
        market_condition: MarketCondition | None = None,
        news_state: str | None = None,
        correlation_id: str | None = None,
    ) -> RiskDecision:
        """
        Evaluate whether a new trade entry is permitted.
        Returns RiskDecision. Caller must check decision.trading_allowed.
        """
        cid = correlation_id or str(uuid.uuid4())

        # 1. Emergency stop overrides everything
        if self._config.emergency_stop_active:
            logger.warning("risk.emergency_stop", account_id=snapshot.account_id, cid=cid)
            return RiskDecision(
                decision=SignalDecision.EMERGENCY,
                reason_code="EMERGENCY_STOP_ACTIVE",
                risk_state=RiskState.EMERGENCY_STOP,
                account_id=snapshot.account_id,
                correlation_id=cid,
                equity_at_decision=snapshot.current_equity_usd,
            )

        # 2. NOT_CONFIGURED if required parameters missing
        if not self._config.is_fully_configured:
            logger.info(
                "risk.not_configured",
                account_id=snapshot.account_id,
                missing=self._config.missing_parameters,
                cid=cid,
            )
            return RiskDecision(
                decision=SignalDecision.NOT_CONFIGURED,
                reason_code=f"MISSING_PARAMETERS:{','.join(self._config.missing_parameters)}",
                risk_state=RiskState.NOT_CONFIGURED,
                account_id=snapshot.account_id,
                correlation_id=cid,
            )

        # 3. Market data health and freshness checks
        if market_condition is not None:
            if market_condition.market_data_status not in ("READY", "OK"):
                return RiskDecision(
                    decision=SignalDecision.BLOCKED,
                    reason_code=f"MARKET_DATA_NOT_READY:{market_condition.market_data_status}",
                    risk_state=RiskState.CAUTION,
                    account_id=snapshot.account_id,
                    correlation_id=cid,
                    equity_at_decision=snapshot.current_equity_usd,
                )

            # Tick staleness
            staleness_ms = market_condition.tick_age_ms
            if staleness_ms is None and market_condition.tick_timestamp is not None:
                staleness_ms = int((datetime.now(UTC) - market_condition.tick_timestamp).total_seconds() * 1000)
            if staleness_ms is not None and staleness_ms > self._config.max_tick_staleness_ms:
                return RiskDecision(
                    decision=SignalDecision.BLOCKED,
                    reason_code="STALE_MARKET_DATA",
                    risk_state=RiskState.CAUTION,
                    account_id=snapshot.account_id,
                    correlation_id=cid,
                    equity_at_decision=snapshot.current_equity_usd,
                )

            # Spread check
            spread = market_condition.effective_spread
            if self._config.max_spread_usd is not None and spread is not None and spread > self._config.max_spread_usd:
                return RiskDecision(
                    decision=SignalDecision.BLOCKED,
                    reason_code="SPREAD_TOO_HIGH",
                    risk_state=RiskState.CAUTION,
                    account_id=snapshot.account_id,
                    correlation_id=cid,
                    equity_at_decision=snapshot.current_equity_usd,
                )

        # 4. News protection filter (fail-closed)
        if news_state is not None:
            if news_state in ("PRE_EVENT", "IN_EVENT", "POST_EVENT"):
                return RiskDecision(
                    decision=SignalDecision.BLOCKED,
                    reason_code=f"NEWS_EVENT_WINDOW:{news_state}",
                    risk_state=RiskState.CAUTION,
                    account_id=snapshot.account_id,
                    correlation_id=cid,
                    equity_at_decision=snapshot.current_equity_usd,
                )
            if news_state in ("UNKNOWN", "PROVIDER_UNAVAILABLE", "STALE"):
                return RiskDecision(
                    decision=SignalDecision.BLOCKED,
                    reason_code=f"NEWS_DATA_UNAVAILABLE:{news_state}",
                    risk_state=RiskState.CAUTION,
                    account_id=snapshot.account_id,
                    correlation_id=cid,
                    equity_at_decision=snapshot.current_equity_usd,
                )

        daily_limit = self._config.daily_loss_limit_usd
        max_dd = self._config.max_drawdown_usd
        max_pos = self._config.max_open_positions

        # 5. Daily loss limit — total daily PNL (realized + floating)
        total_daily_pnl = snapshot.daily_realized_pnl_usd + snapshot.daily_floating_pnl_usd
        if daily_limit is not None and total_daily_pnl <= -daily_limit:
            logger.warning(
                "risk.daily_limit_hit",
                account_id=snapshot.account_id,
                daily_pnl=str(total_daily_pnl),
                limit=str(daily_limit),
            )
            return RiskDecision(
                decision=SignalDecision.BLOCKED,
                reason_code="DAILY_LOSS_LIMIT_HIT",
                risk_state=RiskState.STOPPED,
                account_id=snapshot.account_id,
                correlation_id=cid,
                equity_at_decision=snapshot.current_equity_usd,
                daily_pnl_at_decision=total_daily_pnl,
            )

        # 6. Max drawdown from lifetime HWM (LOCKED: LIFETIME_HWM)
        drawdown = snapshot.equity_peak_usd - snapshot.current_equity_usd
        if max_dd is not None:
            if drawdown >= max_dd:
                logger.warning(
                    "risk.max_drawdown_hit",
                    account_id=snapshot.account_id,
                    drawdown=str(drawdown),
                    limit=str(max_dd),
                )
                return RiskDecision(
                    decision=SignalDecision.BLOCKED,
                    reason_code="MAX_DRAWDOWN_HIT",
                    risk_state=RiskState.STOPPED,
                    account_id=snapshot.account_id,
                    correlation_id=cid,
                    equity_at_decision=snapshot.current_equity_usd,
                    drawdown_at_decision=drawdown,
                )
            if self._config.caution_drawdown_pct is not None:
                caution_limit = max_dd * self._config.caution_drawdown_pct
                if drawdown >= caution_limit:
                    return RiskDecision(
                        decision=SignalDecision.BLOCKED,
                        reason_code="CAUTION_DRAWDOWN_REACHED",
                        risk_state=RiskState.CAUTION,
                        account_id=snapshot.account_id,
                        correlation_id=cid,
                        equity_at_decision=snapshot.current_equity_usd,
                        drawdown_at_decision=drawdown,
                    )

        # 7. Profit-lock floor breach (LOCKED: PCT_RETRACE, FLOATING_EQUITY basis)
        pl_status: ProfitLockStatus | None = None
        if snapshot.session_open_equity_usd is not None and snapshot.session_peak_profit_usd is not None:
            session_profit = snapshot.current_equity_usd - snapshot.session_open_equity_usd
            peak_profit = snapshot.session_peak_profit_usd
            is_active = peak_profit >= self._config.profit_lock_threshold_usd
            protected_floor = peak_profit * self._config.profit_lock_floor_pct if is_active else Decimal("0")
            is_breached = is_active and (session_profit < protected_floor)
            pl_status = ProfitLockStatus(
                is_active=is_active,
                session_profit_usd=session_profit,
                peak_profit_usd=peak_profit,
                protected_floor_usd=protected_floor,
                is_breached=is_breached,
            )
            if is_breached:
                logger.warning(
                    "risk.profit_lock_breached",
                    account_id=snapshot.account_id,
                    session_profit=str(session_profit),
                    protected_floor=str(protected_floor),
                    peak=str(peak_profit),
                )
                return RiskDecision(
                    decision=SignalDecision.BLOCKED,
                    reason_code="PROFIT_LOCK_FLOOR_BREACHED",
                    risk_state=RiskState.PROTECTED,
                    account_id=snapshot.account_id,
                    correlation_id=cid,
                    equity_at_decision=snapshot.current_equity_usd,
                    daily_pnl_at_decision=total_daily_pnl,
                    profit_lock_status=pl_status,
                )

        # 8. Max open positions
        if max_pos is not None and snapshot.open_position_count >= max_pos:
            logger.info(
                "risk.max_positions_reached",
                account_id=snapshot.account_id,
                open=snapshot.open_position_count,
                max=max_pos,
            )
            return RiskDecision(
                decision=SignalDecision.BLOCKED,
                reason_code="MAX_POSITIONS_REACHED",
                risk_state=RiskState.CAUTION,
                account_id=snapshot.account_id,
                correlation_id=cid,
                equity_at_decision=snapshot.current_equity_usd,
                profit_lock_status=pl_status,
            )

        # 9. Position sizing calculation
        authorized_lots: Decimal | None = None
        sizing = self._get_sizing_policy()
        if candidate_signal is not None and sizing is not None:
            entry_p = getattr(candidate_signal, "entry_reference", None)
            sl_p = getattr(candidate_signal, "suggested_stop_loss", None)
            authorized_lots = sizing.calculate_lot_size(
                equity_usd=snapshot.current_equity_usd,
                entry_price=entry_p,
                stop_loss_price=sl_p,
            )
        if authorized_lots is None and self._config.default_position_size_lots is not None:
            authorized_lots = self._config.default_position_size_lots

        # 10. Max open lots / basket exposure limit
        if self._config.max_open_lots is not None:
            proposed_lots = authorized_lots or Decimal("0")
            total_lots = snapshot.open_lot_exposure + snapshot.in_flight_lot_exposure + proposed_lots
            if total_lots > self._config.max_open_lots:
                return RiskDecision(
                    decision=SignalDecision.BLOCKED,
                    reason_code="MAX_LOTS_EXCEEDED",
                    risk_state=RiskState.CAUTION,
                    account_id=snapshot.account_id,
                    correlation_id=cid,
                    equity_at_decision=snapshot.current_equity_usd,
                    profit_lock_status=pl_status,
                )

        # All checks passed
        logger.info(
            "risk.approved",
            account_id=snapshot.account_id,
            equity=str(snapshot.current_equity_usd),
            daily_pnl=str(total_daily_pnl),
        )
        return RiskDecision(
            decision=SignalDecision.APPROVED,
            reason_code="ALL_CHECKS_PASSED",
            risk_state=RiskState.NORMAL,
            account_id=snapshot.account_id,
            correlation_id=cid,
            equity_at_decision=snapshot.current_equity_usd,
            drawdown_at_decision=drawdown,
            daily_pnl_at_decision=total_daily_pnl,
            profit_lock_status=pl_status,
            authorized_lot_size=authorized_lots,
        )
