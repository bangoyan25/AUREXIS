"""
Strategy Engine Service — Phase 4B.

Orchestrates automated signal generation and execution for enabled accounts.

SAFETY INVARIANTS:
1. Strategy only runs when explicitly enabled (enabled=True in StrategyEngineState).
2. Default state is DISABLED. Nothing trades after deployment.
3. Default mode is DRY-RUN. No execution until dry_run=False is set by operator.
4. Kill switch (evaluate_risk_gate BLOCK) always prevents execution.
5. DEMO guard: only accounts confirmed DEMO are permitted execution.
6. One-position limit: if an OPEN position exists -> NO new signal -> NO execution.
7. Cooldown: same M15 candle start timestamp never produces two signals.
8. Brain proposes only — never executes directly.
9. Risk Gate is always mandatory before execution.
10. No secrets, no invented thresholds, no invented strategy logic.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.core.logging import get_logger
from backend.db.models.account import TradingAccount
from backend.db.models.execution import Position as DbPosition
from backend.db.models.mt5_agent import MT5Agent
from backend.db.models.signal import CandidateSignal as DbCandidateSignal
from backend.db.models.strategy import StrategyEngineState
from backend.services import agent_commands as cmd_svc
from backend.services import market_data_service
from backend.services.audit import record_audit_event
from backend.services.risk_gate import evaluate_risk_gate
from backend.ws.agent_manager import agent_manager
from backend.ws.agent_protocol import CommandMessage, CommandPayload
from brain.config import default_strat_config
from brain.market_data.multi_timeframe import MultiTimeframeBarManager
from brain.market_data.types import Tick
from brain.pipeline import SignalPipeline
from brain.strategy.interfaces import SignalDirection

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("strategy.service")

CANONICAL_SYMBOL = "XAUUSD"
PRIMARY_TIMEFRAME = "M15"
STRATEGY_VERSION = "AUREXIS-STRAT-1.0.0"
STRATEGY_ID = "AUREXIS_CORE"

_bar_managers: dict[str, MultiTimeframeBarManager] = {}
_signal_pipeline: SignalPipeline | None = None


def _get_bar_manager(account_id: str) -> MultiTimeframeBarManager:
    if account_id not in _bar_managers:
        config = default_strat_config()
        max_spread = config.spread.max_spread_usd or Decimal("1.00")
        _bar_managers[account_id] = MultiTimeframeBarManager(
            symbol=CANONICAL_SYMBOL,
            timeframes=("M5", PRIMARY_TIMEFRAME, "H1"),
            max_spread_usd=max_spread,
            staleness_threshold_seconds=10.0,
        )
    return _bar_managers[account_id]


def _get_signal_pipeline() -> SignalPipeline:
    global _signal_pipeline
    if _signal_pipeline is None:
        _signal_pipeline = SignalPipeline(
            strategy_id=STRATEGY_ID,
            strategy_version=STRATEGY_VERSION,
            config=default_strat_config(),
        )
    return _signal_pipeline


def _is_confirmed_demo(account: TradingAccount) -> bool:
    server = (account.mt5_server or "").lower()
    broker = (account.broker or "").lower()
    label = (account.label or "").lower()
    if "real" in server or "live" in server:
        return False
    return "demo" in server or "demo" in broker or "demo" in label


def _parse_tick_time(raw_ts: str | None, default_iso: str) -> datetime:
    """Safely parse MT5 tick_time (e.g. '2026.09.11 07:12:19') or fallback to received_at."""
    if not raw_ts:
        dt = datetime.fromisoformat(default_iso)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    # MT5 commonly formats as YYYY.MM.DD HH:MM:SS
    cleaned = raw_ts.strip().replace(".", "-")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            dt = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = datetime.fromisoformat(default_iso)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)



async def get_or_create_strategy_state(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> StrategyEngineState:
    stmt = select(StrategyEngineState).where(
        StrategyEngineState.account_id == account_id
    )
    res = await session.execute(stmt)
    state = res.scalar_one_or_none()
    if state is None:
        state = StrategyEngineState(
            id=uuid.uuid4(),
            account_id=account_id,
            enabled=False,
            dry_run=True,
            strategy_id=STRATEGY_ID,
            strategy_version=STRATEGY_VERSION,
            symbol=CANONICAL_SYMBOL,
            timeframe=PRIMARY_TIMEFRAME,
        )
        session.add(state)
        await session.flush()
    return state


async def enable_strategy(
    session: AsyncSession,
    account_id: uuid.UUID,
    dry_run: bool = True,
) -> StrategyEngineState:
    state = await get_or_create_strategy_state(session, account_id)
    state.enabled = True
    state.dry_run = dry_run
    await session.flush()
    logger.info(
        "strategy.enabled",
        account_id=str(account_id),
        dry_run=dry_run,
    )
    await record_audit_event(
        session=session,
        event_type="STRATEGY_ENABLED",
        account_id=account_id,
        payload={"dry_run": dry_run, "strategy_version": STRATEGY_VERSION},
    )
    return state


async def disable_strategy(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> StrategyEngineState:
    state = await get_or_create_strategy_state(session, account_id)
    state.enabled = False
    await session.flush()
    logger.info("strategy.disabled", account_id=str(account_id))
    await record_audit_event(
        session=session,
        event_type="STRATEGY_DISABLED",
        account_id=account_id,
        payload={"strategy_version": STRATEGY_VERSION},
    )
    return state




async def evaluate_strategy_for_account(
    session: AsyncSession,
    account_id: uuid.UUID,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "account_id": str(account_id),
        "timestamp": datetime.now(UTC).isoformat(),
        "signal_direction": "NONE",
        "signal_reason": None,
        "risk_decision": None,
        "risk_reason_code": None,
        "execution_status": "SKIPPED",
        "execution_reason": None,
        "dry_run": True,
        "candle_ts": None,
        "signal_id": None,
    }

    # Gate 1: Strategy enabled?
    state = await get_or_create_strategy_state(session, account_id)
    result["dry_run"] = state.dry_run
    if not state.enabled:
        result["execution_reason"] = "STRATEGY_DISABLED"
        return result

    # Gate 2: Account exists and is active?
    acct_res = await session.execute(
        select(TradingAccount).where(
            TradingAccount.id == account_id,
            TradingAccount.is_active.is_(True),
        )
    )
    account = acct_res.scalar_one_or_none()
    if account is None:
        result["execution_reason"] = "ACCOUNT_INACTIVE"
        return result

    # Gate 3: If execution mode, DEMO guard
    if not state.dry_run and not _is_confirmed_demo(account):
        state.enabled = False
        state.dry_run = True
        await session.flush()
        logger.critical(
            "strategy.live_execution_blocked_non_demo",
            account_id=str(account_id),
        )
        result["execution_reason"] = "NON_DEMO_ACCOUNT"
        result["execution_status"] = "BLOCKED"
        return result

    # Gate 4: Agent online?
    agent_res = await session.execute(
        select(MT5Agent).where(MT5Agent.account_id == account_id).limit(1)
    )
    agent = agent_res.scalar_one_or_none()
    agent_connected = agent is not None and agent_manager.is_connected(str(agent.id))

    # Gate 5: Market data fresh?
    tick_dict = await market_data_service.get_latest_market_data(account_id, CANONICAL_SYMBOL)
    if tick_dict is None:
        result["execution_reason"] = "NO_MARKET_DATA"
        state.last_risk_decision = "BLOCK"
        state.last_risk_reason_code = "MARKET_DATA_NOT_READY"
        await session.flush()
        return result

    is_fresh, freshness_code, age_ms = market_data_service.evaluate_freshness(
        tick_dict, max_staleness_ms=5000
    )
    if not is_fresh:
        result["execution_reason"] = f"STALE_MARKET_DATA:{freshness_code}"
        state.last_risk_decision = "BLOCK"
        state.last_risk_reason_code = "MARKET_DATA_STALE"
        await session.flush()
        return result

    # Build Tick from market data
    try:
        tick = Tick(
            symbol=CANONICAL_SYMBOL,
            bid=Decimal(tick_dict["bid"]),
            ask=Decimal(tick_dict["ask"]),
            spread=Decimal(tick_dict["spread"]),
            point=Decimal(tick_dict.get("point", "0.01")),
            digits=int(tick_dict.get("digits", 2)),
            tick_time=_parse_tick_time(tick_dict.get("tick_time"), tick_dict["received_at"]),
            volume=Decimal("1"),
        )
    except Exception as exc:
        logger.warning("strategy.tick_parse_error", error=str(exc), account_id=str(account_id))
        result["execution_reason"] = "TICK_PARSE_ERROR"
        return result

    # Gate 6: One-position limit — no new entry if OPEN position exists
    open_pos_res = await session.execute(
        select(DbPosition).where(
            DbPosition.account_id == account_id,
            DbPosition.status == "OPEN",
        ).limit(1)
    )
    open_pos = open_pos_res.scalar_one_or_none()
    if open_pos is not None:
        result["execution_reason"] = "POSITION_ALREADY_OPEN"
        result["signal_reason"] = "POSITION_ALREADY_OPEN"
        return result

    # Gate 7: Build bar from tick, check M15 cooldown
    bar_manager = _get_bar_manager(str(account_id))
    try:
        bar_manager.ingest_tick(tick)
    except ValueError:
        result["execution_reason"] = "TICK_REJECTED_BY_BAR_MANAGER"
        return result

    closed_bars = bar_manager.get_closed_bars(PRIMARY_TIMEFRAME)
    if not closed_bars:
        result["execution_reason"] = "BARS_WARMING_UP"
        return result

    last_closed_bar = closed_bars[-1]
    candle_ts = last_closed_bar.open_time
    if candle_ts.tzinfo is None:
        candle_ts = candle_ts.replace(tzinfo=UTC)
    result["candle_ts"] = candle_ts.isoformat()

    # Cooldown: same M15 candle already processed?
    if (
        state.last_signal_candle_ts is not None
        and state.last_signal_candle_ts.replace(tzinfo=UTC) >= candle_ts
    ):
        result["execution_reason"] = "CANDLE_COOLDOWN"
        result["signal_reason"] = "SAME_CANDLE_ALREADY_PROCESSED"
        return result


    # Gate 8: Brain signal
    pipeline = _get_signal_pipeline()
    brain_signal = pipeline.process(
        latest_tick=tick,
        closed_bars=closed_bars,
        news_state="CLEAR",
        correlation_id=None,
    )

    result["signal_direction"] = brain_signal.direction.value
    result["signal_reason"] = brain_signal.market_state_summary

    if brain_signal.direction == SignalDirection.NONE or not brain_signal.is_configured:
        state.last_signal_direction = "NONE"
        state.last_signal_at = datetime.now(UTC)
        state.last_signal_candle_ts = candle_ts
        state.last_signal_reason = brain_signal.market_state_summary
        await session.flush()
        result["execution_status"] = "NO_SIGNAL"
        return result

    # Stage 9: Persist CandidateSignal to DB
    signal_id = uuid.uuid4()
    entry_ref = brain_signal.entry_reference or (tick.ask if brain_signal.direction == SignalDirection.BUY else tick.bid)
    db_signal = DbCandidateSignal(
        id=signal_id,
        account_id=account_id,
        correlation_id=str(signal_id),
        symbol=CANONICAL_SYMBOL,
        direction=brain_signal.direction.value,
        strategy_id=STRATEGY_ID,
        strategy_version=STRATEGY_VERSION,
        setup_type=brain_signal.setup_type,
        confidence_score=brain_signal.confidence_score,
        entry_reference=entry_ref,
        suggested_stop_loss=brain_signal.suggested_stop_loss,
        suggested_take_profit=brain_signal.suggested_take_profit,
        spread_at_signal=tick.spread,
        news_state_at_signal="CLEAR",
        status="PROPOSED",
        generated_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    session.add(db_signal)
    await session.flush()
    result["signal_id"] = str(signal_id)

    # Gate 10: Risk Gate — mandatory
    gate = await evaluate_risk_gate(session, account_id, CANONICAL_SYMBOL)
    result["risk_decision"] = gate.decision
    result["risk_reason_code"] = gate.reason_code

    state.last_signal_direction = brain_signal.direction.value
    state.last_signal_at = datetime.now(UTC)
    state.last_signal_candle_ts = candle_ts
    state.last_signal_id = signal_id
    state.last_signal_reason = brain_signal.market_state_summary
    state.last_risk_decision = gate.decision
    state.last_risk_reason_code = gate.reason_code

    await record_audit_event(
        session=session,
        event_type="STRATEGY_SIGNAL_EVALUATED",
        account_id=account_id,
        payload={
            "signal_id": str(signal_id),
            "direction": brain_signal.direction.value,
            "candle_ts": candle_ts.isoformat(),
            "risk_decision": gate.decision,
            "risk_reason_code": gate.reason_code,
            "dry_run": state.dry_run,
        },
    )

    if gate.decision != "ALLOW":
        db_signal.status = f"BLOCKED_{gate.reason_code}"
        state.last_execution_status = "BLOCKED"
        await session.flush()
        result["execution_status"] = "BLOCKED"
        result["execution_reason"] = gate.reason_code
        return result


    # Gate 11: Dry-run vs live execution
    if state.dry_run:
        db_signal.status = "DRY_RUN"
        state.last_execution_status = "DRY_RUN"
        await session.flush()
        result["execution_status"] = "DRY_RUN"
        result["execution_reason"] = "DRY_RUN_MODE_ACTIVE"
        logger.info(
            "strategy.dry_run_signal",
            account_id=str(account_id),
            direction=brain_signal.direction.value,
            signal_id=str(signal_id),
            candle_ts=candle_ts.isoformat(),
        )
        return result

    # Live execution: dispatch via agent_manager
    if agent is None or not agent_connected:
        db_signal.status = "BLOCKED_AGENT_OFFLINE"
        state.last_execution_status = "BLOCKED"
        await session.flush()
        result["execution_status"] = "BLOCKED"
        result["execution_reason"] = "AGENT_OFFLINE"
        return result

    side = brain_signal.direction.value
    volume = Decimal("0.01")
    sl = brain_signal.suggested_stop_loss
    tp = brain_signal.suggested_take_profit

    payload: dict[str, Any] = {
        "action": "OPEN_POSITION",
        "symbol": CANONICAL_SYMBOL,
        "side": side,
        "volume": str(volume),
        "price": str(entry_ref),
        "client_order_id": str(signal_id),
        "deviation": 20,
        "comment": f"AUREXIS_4B_{signal_id}",
    }
    if sl is not None:
        payload["stop_loss"] = str(sl)
    if tp is not None:
        payload["take_profit"] = str(tp)

    try:
        cmd = await cmd_svc.create_command(
            db=session,
            agent_id=agent.id,
            command_type="OPEN_POSITION",
            payload=payload,
            account_id=account_id,
        )
        await session.flush()

        cmd = await cmd_svc.mark_sent(
            db=session,
            agent_id=agent.id,
            command_id=cmd.id,
            account_id=account_id,
        )

        msg = CommandMessage(
            command=CommandPayload(
                id=str(cmd.id),
                command_type="OPEN_POSITION",
                payload=payload,
            )
        )
        delivered = await agent_manager.send_json(str(agent.id), msg.model_dump())
        if not delivered:
            await cmd_svc.fail_command(
                db=session,
                agent_id=agent.id,
                command_id=cmd.id,
                error_message="WebSocket delivery failed",
                account_id=account_id,
            )
            db_signal.status = "BLOCKED_AGENT_OFFLINE"
            state.last_execution_status = "FAILED"
            await session.flush()
            result["execution_status"] = "FAILED"
            result["execution_reason"] = "AGENT_WS_DELIVERY_FAILED"
            return result

        db_signal.status = "EXECUTION_PENDING"
        state.last_execution_status = "PENDING"
        await session.flush()
        result["execution_status"] = "EXECUTION_PENDING"
        result["command_id"] = str(cmd.id)
        logger.info(
            "strategy.execution_dispatched",
            account_id=str(account_id),
            signal_id=str(signal_id),
            command_id=str(cmd.id),
            direction=side,
        )

    except Exception as exc:
        logger.error(
            "strategy.execution_error",
            account_id=str(account_id),
            signal_id=str(signal_id),
            error=str(exc),
        )
        db_signal.status = "EXECUTION_FAILED"
        state.last_execution_status = "ERROR"
        await session.flush()
        result["execution_status"] = "ERROR"
        result["execution_reason"] = str(exc)

    return result


def clear_bar_managers() -> None:
    """Clear in-process bar managers and pipeline cache. Used in tests."""
    _bar_managers.clear()
    global _signal_pipeline
    _signal_pipeline = None

