"""
Risk Service layer.

Coordinates:
- Loading versioned RiskConfiguration from PostgreSQL
- Computing AccountRiskSnapshot from PostgreSQL state
- Evaluating RiskEngine
- Persisting immutable RiskDecision to PostgreSQL
- Writing audit log trail
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, func, select

from backend.db.models.equity import DailySessionState, EquitySnapshot
from backend.db.models.execution import Position
from backend.db.models.risk import RiskConfiguration
from backend.db.models.risk import RiskDecision as RiskDecisionModel
from backend.risk.config import RiskConfig
from backend.risk.engine import AccountRiskSnapshot, MarketCondition, RiskDecision, RiskEngine
from backend.services.audit import record_audit_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def get_latest_risk_config(session: AsyncSession, account_id: uuid.UUID) -> RiskConfig:
    """Fetch the latest active RiskConfiguration for an account, or an unconfigured default."""
    stmt = (
        select(RiskConfiguration)
        .where(RiskConfiguration.account_id == account_id)
        .order_by(desc(RiskConfiguration.version))
        .limit(1)
    )
    result = await session.execute(stmt)
    db_config = result.scalar_one_or_none()

    if db_config is None:
        return RiskConfig()

    return RiskConfig(
        daily_loss_limit_usd=db_config.daily_loss_limit_usd,
        max_drawdown_usd=db_config.max_drawdown_usd,
        max_open_positions=db_config.max_open_positions,
        max_open_lots=db_config.max_open_lots,
        max_spread_usd=db_config.max_spread_usd,
        risk_per_trade_pct=db_config.risk_per_trade_pct,
        profit_lock_threshold_usd=db_config.profit_lock_threshold_usd,
        profit_lock_floor_pct=db_config.profit_lock_floor_pct,
        max_tick_staleness_ms=db_config.max_tick_staleness_ms,
        news_pre_event_window_minutes=db_config.news_pre_event_window_minutes,
        news_post_event_window_minutes=db_config.news_post_event_window_minutes,
        daily_reset_timezone=db_config.daily_reset_timezone,
        emergency_stop_active=getattr(db_config, "kill_switch_active", False),
    )


async def build_account_risk_snapshot(session: AsyncSession, account_id: uuid.UUID) -> AccountRiskSnapshot:
    """Build AccountRiskSnapshot from authoritative PostgreSQL state."""
    eq_stmt = (
        select(EquitySnapshot)
        .where(EquitySnapshot.account_id == account_id)
        .order_by(desc(EquitySnapshot.snapped_at))
        .limit(1)
    )
    eq_res = await session.execute(eq_stmt)
    latest_eq = eq_res.scalar_one_or_none()

    current_balance = latest_eq.balance_usd if latest_eq else Decimal("0")
    current_equity = latest_eq.equity_usd if latest_eq else Decimal("0")

    hwm_stmt = (
        select(func.max(EquitySnapshot.equity_usd))
        .where(EquitySnapshot.account_id == account_id)
    )
    hwm_res = await session.execute(hwm_stmt)
    peak_equity = hwm_res.scalar() or current_equity
    if peak_equity < current_equity:
        peak_equity = current_equity

    today = datetime.now(UTC).date()
    session_stmt = (
        select(DailySessionState)
        .where(
            DailySessionState.account_id == account_id,
            DailySessionState.session_date == today,
        )
    )
    session_res = await session.execute(session_stmt)
    daily_state = session_res.scalar_one_or_none()

    daily_realized = daily_state.realized_pnl_usd if daily_state else Decimal("0")
    daily_floating = daily_state.floating_pnl_usd if daily_state and daily_state.floating_pnl_usd is not None else Decimal("0")
    session_open_eq = daily_state.session_open_equity_usd if daily_state else current_equity
    session_peak_prof = daily_state.session_peak_profit_usd if daily_state else Decimal("0")

    pos_stmt = (
        select(Position)
        .where(
            Position.account_id == account_id,
            Position.status == "OPEN",
        )
    )
    pos_res = await session.execute(pos_stmt)
    open_positions = pos_res.scalars().all()

    open_pos_count = len(open_positions)
    open_lots = sum((p.lots for p in open_positions), Decimal("0"))

    return AccountRiskSnapshot(
        account_id=str(account_id),
        current_balance_usd=current_balance,
        current_equity_usd=current_equity,
        equity_peak_usd=peak_equity,
        daily_realized_pnl_usd=daily_realized,
        daily_floating_pnl_usd=daily_floating,
        open_position_count=open_pos_count,
        snapshot_at=datetime.now(UTC),
        session_open_equity_usd=session_open_eq,
        session_peak_profit_usd=session_peak_prof,
        open_lot_exposure=open_lots,
        in_flight_lot_exposure=Decimal("0"),
    )


async def evaluate_and_record_risk(
    session: AsyncSession,
    account_id: uuid.UUID,
    candidate_signal: Any | None = None,
    market_condition: MarketCondition | None = None,
    news_state: str | None = None,
    correlation_id: str | None = None,
) -> RiskDecision:
    """Authoritatively evaluate risk and persist immutable RiskDecision audit trail in DB."""
    config = await get_latest_risk_config(session, account_id)
    snapshot = await build_account_risk_snapshot(session, account_id)

    engine = RiskEngine(config=config)
    decision = engine.evaluate(
        snapshot=snapshot,
        candidate_signal=candidate_signal,
        market_condition=market_condition,
        news_state=news_state,
        correlation_id=correlation_id,
    )

    signal_id_uuid: uuid.UUID | None = None
    if candidate_signal and hasattr(candidate_signal, "id") and candidate_signal.id:
        try:
            signal_id_uuid = uuid.UUID(str(candidate_signal.id))
        except ValueError:
            signal_id_uuid = None

    db_decision = RiskDecisionModel(
        account_id=account_id,
        signal_id=signal_id_uuid,
        correlation_id=decision.correlation_id,
        decision=decision.decision.value,
        reason_code=decision.reason_code,
        risk_state=decision.risk_state.value,
        equity_at_decision=decision.equity_at_decision,
        drawdown_at_decision=decision.drawdown_at_decision,
        daily_pnl_at_decision=decision.daily_pnl_at_decision,
        profit_lock_active=decision.profit_lock_status.is_active if decision.profit_lock_status else False,
        profit_lock_floor_usd=decision.profit_lock_status.protected_floor_usd if decision.profit_lock_status else None,
        decided_at=decision.decided_at,
    )
    session.add(db_decision)

    await record_audit_event(
        session=session,
        event_type="RISK_EVALUATED",
        account_id=account_id,
        payload={
            "decision": decision.decision.value,
            "reason_code": decision.reason_code,
            "risk_state": decision.risk_state.value,
            "trading_allowed": decision.trading_allowed,
            "authorized_lot_size": str(decision.authorized_lot_size) if decision.authorized_lot_size else None,
        },
    )
    await session.commit()

    return decision
