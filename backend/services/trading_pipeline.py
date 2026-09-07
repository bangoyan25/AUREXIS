"""
Canonical End-to-End Trading Pipeline Service — Stage D.

Orchestrates:
  MultiTimeframeBarManager (Tick ingestion → M5/M15/H1 closed bars)
    → Brain SignalPipeline (CandidateSignal proposal)
    → CandidateSignal persistence in PostgreSQL
    → Risk Service / Risk Engine (Fail-closed authority → RiskDecision)
    → Execution Service (ExecutionCommand → MT5AgentSimulator → ExecutionReport)
    → Reconciliation Engine (Server positions vs broker/simulator state)
    → Position persistence & state updates
    → WebSocket event broadcasts
    → Immutable audit trail recording

CRITICAL SAFETY INVARIANTS:
1. Brain ONLY proposes CandidateSignal; NEVER creates ExecutionCommand directly.
2. CandidateSignal without Risk APPROVED → NO order sent.
3. Fail-closed: non-READY market data, expired signal, stale tick, emergency stop,
   or critical reconciliation discrepancy → NO trade entry.
4. Reconciliation Circuit Breaker: critical discrepancy freezes account for new entries.
5. Idempotent dispatch: duplicate idempotency keys return without duplicate broker action.
6. Execution runs ONLY via MT5AgentSimulator in SIMULATION mode; live broker unreachable.
7. trading_enabled=False remains enforced; pipeline never toggles it.
8. No new trading parameters are invented here; all parameters come from Brain/Risk config.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from backend.core.logging import get_logger
from backend.db.models.signal import CandidateSignal as DbCandidateSignal
from backend.execution.reconciliation import ReconciliationResult
from backend.execution.simulator import MT5AgentSimulator
from backend.risk.engine import MarketCondition, RiskDecision
from backend.risk.states import SignalDecision
from backend.services.audit import AuditEventType, Severity, record_audit_event
from backend.services.execution_service import ExecutionService
from backend.services.risk_service import evaluate_and_record_risk
from backend.ws.events import (
    WsEvent,
    make_command_created_event,
    make_command_updated_event,
    make_position_updated_event,
    make_risk_state_changed_event,
    make_signal_created_event,
    make_system_alert_event,
)
from brain.market_data.multi_timeframe import MultiTimeframeBarManager
from brain.market_data.types import Tick
from brain.pipeline import SignalPipeline
from brain.strategy.interfaces import SignalDirection

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.db.models.execution import ExecutionReport as DbExecutionReport
    from backend.ws.manager import ConnectionManager

logger = get_logger("trading.pipeline")

PIPELINE_STATUS_INVALID_TICK = "INVALID_TICK"
PIPELINE_STATUS_MARKET_NOT_READY = "MARKET_DATA_NOT_READY"
PIPELINE_STATUS_ACCOUNT_FROZEN = "ACCOUNT_FROZEN"
PIPELINE_STATUS_SIGNAL_NONE = "SIGNAL_NONE"
PIPELINE_STATUS_SIGNAL_EXPIRED = "SIGNAL_EXPIRED"
PIPELINE_STATUS_RISK_BLOCKED = "RISK_BLOCKED"
PIPELINE_STATUS_RISK_NOT_CONFIGURED = "RISK_NOT_CONFIGURED"
PIPELINE_STATUS_RISK_EMERGENCY = "RISK_EMERGENCY"
PIPELINE_STATUS_EXECUTION_REJECTED = "EXECUTION_REJECTED"
PIPELINE_STATUS_EXECUTION_FILLED = "EXECUTION_FILLED"
PIPELINE_STATUS_EXECUTION_EXPIRED = "EXECUTION_EXPIRED"


@dataclass(frozen=True)
class PipelineCycleResult:
    """Structured outcome of a single tick processing cycle."""
    correlation_id: str
    symbol: str
    status: str
    tick: Tick
    candidate_signal: DbCandidateSignal | None = None
    risk_decision: RiskDecision | None = None
    execution_report: DbExecutionReport | None = None
    reconciliation_result: ReconciliationResult | None = None
    events_emitted: list[WsEvent] = field(default_factory=list)
    detail: str = ""


class TradingPipeline:
    """
    Canonical orchestrator for the AUREXIS trading simulation pipeline.
    One instance per (account_id x symbol) for clean state isolation.
    """

    MODE: str = "SIMULATION"

    def __init__(
        self,
        account_id: uuid.UUID,
        symbol: str = "XAUUSD",
        bar_manager: MultiTimeframeBarManager | None = None,
        brain_pipeline: SignalPipeline | None = None,
        simulator: MT5AgentSimulator | None = None,
        execution_service: ExecutionService | None = None,
        ws_manager: ConnectionManager | None = None,
        primary_timeframe: str = "M5",
        signal_expiry_seconds: int = 60,
    ) -> None:
        self.account_id = account_id
        self.symbol = symbol
        self.primary_timeframe = primary_timeframe
        self.signal_expiry_seconds = signal_expiry_seconds

        self.bar_manager = bar_manager or MultiTimeframeBarManager(symbol=symbol)
        self.brain_pipeline = brain_pipeline or SignalPipeline()
        self.simulator = simulator or MT5AgentSimulator()
        self.execution_service = execution_service or ExecutionService(simulator=self.simulator)
        self.ws_manager = ws_manager

        self._frozen_accounts: dict[uuid.UUID, str] = {}

    def freeze_account(self, account_id: uuid.UUID, reason: str) -> None:
        """Freeze trading for an account due to critical reconciliation discrepancy."""
        self._frozen_accounts[account_id] = reason
        logger.critical(
            "pipeline.account_frozen",
            account_id=str(account_id),
            reason=reason,
        )

    def unfreeze_account(self, account_id: uuid.UUID) -> None:
        """Unfreeze account (operator-initiated only)."""
        self._frozen_accounts.pop(account_id, None)
        logger.info("pipeline.account_unfrozen", account_id=str(account_id))

    def is_account_frozen(self, account_id: uuid.UUID) -> bool:
        return account_id in self._frozen_accounts

    def warm_up_from_ticks(self, ticks: list[Tick]) -> int:
        """Feed historical ticks to build bar history without producing signals."""
        count = 0
        for tick in ticks:
            val = self.bar_manager.validate_tick(tick)
            if not val.is_valid:
                continue
            try:
                self.bar_manager.ingest_tick(tick)
                count += 1
            except Exception as exc:  # pragma: no cover
                logger.warning("pipeline.warmup_ingest_error", error=str(exc))
        return count

    async def _emit(self, event: WsEvent, events: list[WsEvent]) -> None:
        events.append(event)
        if self.ws_manager is not None:
            try:
                await self.ws_manager.broadcast_event(event)
            except Exception as exc:  # pragma: no cover
                logger.warning("pipeline.ws_broadcast_error", error=str(exc))


    async def process_tick(
        self,
        session: AsyncSession,
        tick: Tick,
        news_state: str = "CLEAR",
        correlation_id: str | None = None,
    ) -> PipelineCycleResult:
        """Run one complete pipeline cycle for a single incoming tick."""
        cid = correlation_id or str(uuid.uuid4())
        account_id = self.account_id
        events_emitted: list[WsEvent] = []

        # Gate 1: Tick validation
        val = self.bar_manager.validate_tick(tick)
        if not val.is_valid:
            logger.debug("pipeline.invalid_tick", correlation_id=cid, reason=val.error_message)
            return PipelineCycleResult(
                correlation_id=cid, symbol=self.symbol,
                status=PIPELINE_STATUS_INVALID_TICK, tick=tick,
                detail=val.error_message or "",
            )
        self.bar_manager.ingest_tick(tick)

        # Gate 2: Market data readiness
        if self.bar_manager.is_stale():
            return PipelineCycleResult(
                correlation_id=cid, symbol=self.symbol,
                status=PIPELINE_STATUS_MARKET_NOT_READY, tick=tick, detail="MARKET_STALE",
            )
        if not self.bar_manager.is_spread_acceptable():
            return PipelineCycleResult(
                correlation_id=cid, symbol=self.symbol,
                status=PIPELINE_STATUS_MARKET_NOT_READY, tick=tick, detail="SPREAD_TOO_WIDE",
            )
        closed_bars = self.bar_manager.get_closed_bars(self.primary_timeframe)
        if not closed_bars:
            return PipelineCycleResult(
                correlation_id=cid, symbol=self.symbol,
                status=PIPELINE_STATUS_MARKET_NOT_READY, tick=tick, detail="BARS_WARMING",
            )

        # Gate 3: Reconciliation circuit breaker
        if self.is_account_frozen(account_id):
            return PipelineCycleResult(
                correlation_id=cid, symbol=self.symbol,
                status=PIPELINE_STATUS_ACCOUNT_FROZEN, tick=tick,
                detail=self._frozen_accounts[account_id],
            )

        # Stage 4: Brain signal pipeline (PROPOSE only — never creates ExecutionCommand)
        brain_signal = self.brain_pipeline.process(
            latest_tick=tick, closed_bars=closed_bars,
            news_state=news_state, correlation_id=cid,
        )
        if brain_signal.direction == SignalDirection.NONE or not brain_signal.is_configured:
            await record_audit_event(
                session=session, event_type=AuditEventType.SIGNAL_BLOCKED,
                account_id=account_id, correlation_id=cid,
                payload={"reason": brain_signal.market_state_summary},
            )
            await session.commit()
            return PipelineCycleResult(
                correlation_id=cid, symbol=self.symbol,
                status=PIPELINE_STATUS_SIGNAL_NONE, tick=tick,
                detail=brain_signal.market_state_summary,
            )


        # Stage 5: Persist CandidateSignal to PostgreSQL
        signal_id = uuid.uuid4()
        expires_at = datetime.now(UTC) + timedelta(seconds=self.signal_expiry_seconds)

        evidence_json_str: str | None = None
        if brain_signal.evidence:
            try:
                evidence_json_str = json.dumps(brain_signal.evidence, default=str)
            except Exception:  # pragma: no cover
                evidence_json_str = None

        entry_ref = brain_signal.entry_reference
        if entry_ref is None:
            entry_ref = tick.ask if brain_signal.direction == SignalDirection.BUY else tick.bid

        regime_str: str | None = None
        if brain_signal.evidence and isinstance(brain_signal.evidence, dict):
            regime_str = str(brain_signal.evidence.get("regime", "")) or None

        db_signal = DbCandidateSignal(
            id=signal_id,
            account_id=account_id,
            correlation_id=cid,
            symbol=tick.symbol,
            direction=brain_signal.direction.value,
            strategy_id=brain_signal.strategy_id,
            strategy_version=brain_signal.strategy_version,
            regime=regime_str,
            setup_type=brain_signal.setup_type,
            confidence_score=brain_signal.confidence_score,
            entry_reference=entry_ref,
            suggested_stop_loss=brain_signal.suggested_stop_loss,
            suggested_take_profit=brain_signal.suggested_take_profit,
            spread_at_signal=tick.spread,
            news_state_at_signal=news_state,
            evidence_json=evidence_json_str,
            status="PROPOSED",
            generated_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        session.add(db_signal)
        await session.flush()

        sig_event = make_signal_created_event(
            account_id=str(account_id),
            signal_id=str(db_signal.id),
            symbol=db_signal.symbol,
            direction=db_signal.direction,
            regime=db_signal.regime,
            setup_type=db_signal.setup_type,
            confidence_score=str(db_signal.confidence_score) if db_signal.confidence_score is not None else None,
            expires_at=db_signal.expires_at.isoformat() if db_signal.expires_at else None,
            correlation_id=cid,
        )
        await self._emit(sig_event, events_emitted)
        await record_audit_event(
            session=session, event_type=AuditEventType.SIGNAL_CREATED,
            account_id=account_id, correlation_id=cid,
            payload={"signal_id": str(db_signal.id), "direction": db_signal.direction},
        )

        # Gate 6: Signal expiry check
        if db_signal.expires_at and datetime.now(UTC) > db_signal.expires_at:
            db_signal.status = "EXPIRED"
            await session.commit()
            return PipelineCycleResult(
                correlation_id=cid, symbol=self.symbol,
                status=PIPELINE_STATUS_SIGNAL_EXPIRED, tick=tick,
                candidate_signal=db_signal, events_emitted=events_emitted,
                detail="Signal expired before risk evaluation",
            )

        # Stage 7: Risk evaluation (fail-closed authority)
        market_cond = MarketCondition(
            symbol=tick.symbol,
            bid=tick.bid,
            ask=tick.ask,
            spread=tick.spread,
            tick_timestamp=tick.tick_time,
            tick_age_ms=int(tick.staleness_seconds() * 1000),
            market_data_status="READY",
        )
        risk_decision = await evaluate_and_record_risk(
            session=session,
            account_id=account_id,
            candidate_signal=db_signal,
            market_condition=market_cond,
            news_state=news_state,
            correlation_id=cid,
        )

        risk_event = make_risk_state_changed_event(
            account_id=str(account_id),
            state=risk_decision.risk_state.value,
            trading_allowed=risk_decision.trading_allowed,
            block_reason=risk_decision.reason_code if not risk_decision.trading_allowed else None,
            correlation_id=cid,
        )
        await self._emit(risk_event, events_emitted)


        # Gate 8: Risk decision gating
        # Invariants: NOT_CONFIGURED / BLOCKED / EMERGENCY / not trading_allowed -> no execution
        if (
            risk_decision.decision in (SignalDecision.NOT_CONFIGURED, SignalDecision.BLOCKED, SignalDecision.EMERGENCY)
            or not risk_decision.trading_allowed
        ):
            risk_status_map = {
                SignalDecision.NOT_CONFIGURED: PIPELINE_STATUS_RISK_NOT_CONFIGURED,
                SignalDecision.BLOCKED: PIPELINE_STATUS_RISK_BLOCKED,
                SignalDecision.EMERGENCY: PIPELINE_STATUS_RISK_EMERGENCY,
            }
            risk_status = risk_status_map.get(risk_decision.decision, PIPELINE_STATUS_RISK_BLOCKED)
            db_signal.status = f"BLOCKED_{risk_decision.reason_code}"
            await session.commit()
            logger.info(
                "pipeline.risk_blocked",
                correlation_id=cid, account_id=str(account_id),
                decision=risk_decision.decision.value,
                reason=risk_decision.reason_code,
            )
            return PipelineCycleResult(
                correlation_id=cid, symbol=self.symbol,
                status=risk_status, tick=tick,
                candidate_signal=db_signal, risk_decision=risk_decision,
                events_emitted=events_emitted, detail=risk_decision.reason_code,
            )

        # Stage 9: Execution dispatch (Risk APPROVED)
        # Invariant: Simulation only — live broker unreachable.
        # Invariant: Idempotent — signal-scoped key prevents duplicate broker action.
        idempotency_key = f"exec_{account_id}_{db_signal.id}"
        target_price = tick.ask if db_signal.direction == "BUY" else tick.bid

        cmd_event = make_command_created_event(
            account_id=str(account_id),
            command_id=idempotency_key,
            action="ORDER_OPEN",
            symbol=db_signal.symbol,
            order_type=db_signal.direction,
            volume_lots=str(risk_decision.authorized_lot_size) if risk_decision.authorized_lot_size else "0",
            price=str(target_price),
            correlation_id=cid,
        )
        await self._emit(cmd_event, events_emitted)

        exec_report = await self.execution_service.execute_approved_signal(
            session=session,
            account_id=account_id,
            signal=db_signal,
            decision=risk_decision,
            current_price=target_price,
            correlation_id=cid,
            idempotency_key=idempotency_key,
        )

        if exec_report is None:
            db_signal.status = "EXECUTION_REJECTED"
            await session.commit()
            logger.warning(
                "pipeline.execution_rejected",
                correlation_id=cid, account_id=str(account_id),
                idempotency_key=idempotency_key,
            )
            return PipelineCycleResult(
                correlation_id=cid, symbol=self.symbol,
                status=PIPELINE_STATUS_EXECUTION_REJECTED, tick=tick,
                candidate_signal=db_signal, risk_decision=risk_decision,
                events_emitted=events_emitted, detail="EXECUTION_REJECTED_OR_DUPLICATE",
            )

        exec_status = exec_report.status if isinstance(exec_report.status, str) else str(exec_report.status)
        cmd_updated = make_command_updated_event(
            account_id=str(account_id),
            command_id=str(exec_report.command_id),
            status=exec_status,
            broker_ticket=exec_report.broker_ticket,
            fill_price=str(exec_report.fill_price) if exec_report.fill_price else None,
            fill_volume_lots=str(exec_report.fill_volume_lots) if exec_report.fill_volume_lots else None,
            correlation_id=cid,
        )
        await self._emit(cmd_updated, events_emitted)

        pipeline_status = PIPELINE_STATUS_EXECUTION_FILLED
        if exec_status == "EXPIRED":
            pipeline_status = PIPELINE_STATUS_EXECUTION_EXPIRED
        elif exec_status not in ("FILLED", "PARTIALLY_FILLED"):
            pipeline_status = PIPELINE_STATUS_EXECUTION_REJECTED

        if exec_status in ("FILLED", "PARTIALLY_FILLED") and exec_report.broker_ticket:
            pos_event = make_position_updated_event(
                account_id=str(account_id),
                broker_ticket=exec_report.broker_ticket,
                symbol=db_signal.symbol,
                side=db_signal.direction,
                lots=str(exec_report.fill_volume_lots or risk_decision.authorized_lot_size),
                open_price=str(exec_report.fill_price or target_price),
                current_price=str(exec_report.fill_price or target_price),
                stop_loss=str(db_signal.suggested_stop_loss) if db_signal.suggested_stop_loss else None,
                take_profit=str(db_signal.suggested_take_profit) if db_signal.suggested_take_profit else None,
                status="OPEN",
                correlation_id=cid,
            )
            await self._emit(pos_event, events_emitted)

        db_signal.status = "EXECUTED"


        # Stage 10: Reconciliation
        broker_positions = self.simulator.get_open_positions()
        recon_result = await self.execution_service.reconcile_account_positions(
            session=session,
            account_id=account_id,
            broker_positions=broker_positions,
        )

        if recon_result.has_critical_discrepancy:
            freeze_reason = (
                f"Critical reconciliation: "
                f"{[d.discrepancy_type for d in recon_result.discrepancies]}"
            )
            self.freeze_account(account_id, reason=freeze_reason)
            alert_event = make_system_alert_event(
                message=freeze_reason, severity="CRITICAL", account_id=str(account_id),
            )
            await self._emit(alert_event, events_emitted)
            await record_audit_event(
                session=session, event_type=AuditEventType.RECONCILIATION_MISMATCH,
                account_id=account_id, severity=Severity.CRITICAL,
                correlation_id=cid, payload={"freeze_reason": freeze_reason},
            )
        else:
            await record_audit_event(
                session=session, event_type=AuditEventType.RECONCILIATION_OK,
                account_id=account_id, correlation_id=cid,
                payload={
                    "matched_count": recon_result.matched_count,
                    "discrepancy_count": len(recon_result.discrepancies),
                },
            )

        await session.commit()

        logger.info(
            "pipeline.cycle_complete",
            correlation_id=cid, account_id=str(account_id),
            status=pipeline_status,
            broker_ticket=exec_report.broker_ticket,
        )

        return PipelineCycleResult(
            correlation_id=cid,
            symbol=self.symbol,
            status=pipeline_status,
            tick=tick,
            candidate_signal=db_signal,
            risk_decision=risk_decision,
            execution_report=exec_report,
            reconciliation_result=recon_result,
            events_emitted=events_emitted,
            detail=exec_status,
        )

