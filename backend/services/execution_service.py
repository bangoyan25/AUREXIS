"""
Execution Service layer.

Coordinates:
- Receiving risk-approved candidate signals
- Idempotent generation and persistence of ExecutionCommand
- Dispatching to MT5 agent (or simulator)
- Handling ExecutionReport and updating position records
- Emitting audit log events
- Reconciling position states
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.core.logging import get_logger
from backend.db.models.execution import (
    ExecutionCommand as DbExecutionCommand,
)
from backend.db.models.execution import (
    ExecutionReport as DbExecutionReport,
)
from backend.db.models.execution import (
    Position as DbPosition,
)
from backend.execution.commands import CommandAction, CommandState, ExecutionCommand
from backend.execution.reconciliation import ReconciliationEngine, ReconciliationResult
from backend.execution.reports import ExecutionStatus, PositionReport
from backend.execution.simulator import MT5AgentSimulator
from backend.services.audit import record_audit_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.risk.engine import RiskDecision

logger = get_logger("execution.service")


class ExecutionService:
    """Dispatches authorized execution commands and reconciles broker fills."""

    def __init__(self, simulator: MT5AgentSimulator | None = None) -> None:
        self.simulator = simulator or MT5AgentSimulator()

    async def execute_approved_signal(
        self,
        session: AsyncSession,
        account_id: uuid.UUID,
        signal: Any,
        decision: RiskDecision,
        current_price: Decimal | None = None,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> DbExecutionReport | None:
        """
        Creates, logs, and executes an order command strictly when Risk Engine authorizes it.
        Fail-closed: if decision.trading_allowed is False, refuses to execute.
        Idempotency: if idempotency_key already exists in DB, returns None without re-executing.
        """
        cid = correlation_id or decision.correlation_id or str(uuid.uuid4())

        if not decision.trading_allowed:
            logger.warning("execution.rejected_by_risk", account_id=str(account_id), reason=decision.reason_code)
            return None

        if not decision.authorized_lot_size or decision.authorized_lot_size <= Decimal("0"):
            logger.warning("execution.invalid_authorized_lot_size", account_id=str(account_id))
            return None

        cmd_id = uuid.uuid4()
        derived_idem = idempotency_key or f"cmd_{account_id}_{cmd_id}"

        # Idempotency check: if a command with this key already exists, skip re-execution
        existing_stmt = select(DbExecutionCommand).where(
            DbExecutionCommand.idempotency_key == derived_idem
        )
        existing_res = await session.execute(existing_stmt)
        existing_cmd = existing_res.scalar_one_or_none()
        if existing_cmd is not None:
            logger.warning(
                "execution.duplicate_idempotency_key",
                account_id=str(account_id),
                idempotency_key=derived_idem,
                existing_command_id=str(existing_cmd.id),
            )
            return None
        action = CommandAction.ORDER_OPEN
        sig_dir = getattr(signal, "direction", "BUY")
        dir_str = sig_dir.value if hasattr(sig_dir, "value") else str(sig_dir)
        order_type = "BUY" if "BUY" in dir_str.upper() else "SELL"
        expires_at = datetime.now(UTC) + timedelta(seconds=5)

        mem_command = ExecutionCommand(
            command_id=str(cmd_id),
            account_id=str(account_id),
            action=action,
            symbol=getattr(signal, "symbol", "XAUUSD"),
            order_type="BUY" if order_type == "BUY" else "SELL",
            volume_lots=decision.authorized_lot_size,
            price=current_price or Decimal("2000.00"),
            slippage_points=20,
            idempotency_key=derived_idem,
            expires_at=expires_at,
            correlation_id=cid,
            stop_loss=getattr(signal, "suggested_stop_loss", None),
            take_profit=getattr(signal, "suggested_take_profit", None),
        )

        signal_id_uuid: uuid.UUID | None = None
        if hasattr(signal, "id") and signal.id:
            try:
                signal_id_uuid = uuid.UUID(str(signal.id))
            except ValueError:
                signal_id_uuid = None

        db_cmd = DbExecutionCommand(
            id=cmd_id,
            account_id=account_id,
            signal_id=signal_id_uuid,
            correlation_id=cid,
            idempotency_key=derived_idem,
            action=action.value,
            symbol=mem_command.symbol,
            order_type=order_type,
            volume_lots=decision.authorized_lot_size,
            price=current_price,
            stop_loss=mem_command.stop_loss,
            take_profit=mem_command.take_profit,
            status=CommandState.CREATED.value,
            expires_at=expires_at,
        )
        session.add(db_cmd)
        await session.flush()


        mem_command.transition_to(CommandState.SENT)
        db_cmd.sent_at = datetime.now(UTC)
        db_cmd.status = CommandState.SENT.value

        report = self.simulator.execute_command(mem_command, current_market_price=current_price)

        if report.status == ExecutionStatus.FILLED:
            mem_command.transition_to(CommandState.ACKNOWLEDGED)
            mem_command.transition_to(CommandState.EXECUTING)
            mem_command.transition_to(CommandState.FILLED)
            db_cmd.status = CommandState.FILLED.value
        elif report.status == ExecutionStatus.EXPIRED:
            mem_command.transition_to(CommandState.EXPIRED)
            db_cmd.status = CommandState.EXPIRED.value
        else:
            mem_command.transition_to(CommandState.REJECTED)
            db_cmd.status = CommandState.REJECTED.value

        status_str = report.status.value if hasattr(report.status, "value") else str(report.status)
        db_report = DbExecutionReport(
            account_id=account_id,
            command_id=cmd_id,
            correlation_id=cid,
            idempotency_key=idempotency_key,
            broker_ticket=report.broker_ticket,
            broker_deal_id=report.broker_deal_id,
            status=status_str,
            fill_volume_lots=report.filled_volume_lots,
            fill_price=report.fill_price,
            slippage_points=report.slippage_points,
            commission_usd=report.commission_usd,
            swap_usd=report.swap_usd,
            broker_error_code=report.broker_error_code,
            broker_error_message=report.broker_error_message,
            raw_broker_response_json=json.dumps(report.raw_broker_response) if report.raw_broker_response else None,
            executed_at=report.reported_at,
        )
        session.add(db_report)

        if report.status in (ExecutionStatus.FILLED, "FILLED") and report.broker_ticket:
            db_pos = DbPosition(
                account_id=account_id,
                command_id=cmd_id,
                broker_ticket=report.broker_ticket,
                symbol=mem_command.symbol,
                side=order_type,
                lots=report.filled_volume_lots or decision.authorized_lot_size,
                open_price=report.fill_price or (current_price or Decimal("2000.00")),
                stop_loss=mem_command.stop_loss,
                take_profit=mem_command.take_profit,
                current_price=report.fill_price,
                unrealized_pnl_usd=Decimal("0.00"),
                commission_usd=report.commission_usd or Decimal("0.00"),
                swap_usd=report.swap_usd or Decimal("0.00"),
                status="OPEN",
                opened_at=report.reported_at,
            )
            session.add(db_pos)

        await record_audit_event(
            session=session,
            event_type="COMMAND_DISPATCHED",
            account_id=account_id,
            payload={
                "command_id": str(cmd_id),
                "action": action.value,
                "status": db_cmd.status,
                "broker_ticket": report.broker_ticket,
                "filled_lots": str(report.filled_volume_lots) if report.filled_volume_lots else None,
            },
        )
        await session.commit()
        return db_report

    async def reconcile_account_positions(
        self,
        session: AsyncSession,
        account_id: uuid.UUID,
        broker_positions: list[PositionReport],
    ) -> ReconciliationResult:
        """Run reconciliation between server DB positions and reported broker positions."""
        pos_stmt = (
            select(DbPosition)
            .where(
                DbPosition.account_id == account_id,
                DbPosition.status == "OPEN",
            )
        )
        res = await session.execute(pos_stmt)
        server_positions = list(res.scalars().all())

        server_pos_map: dict[int, dict[str, object]] = {
            p.broker_ticket: {
                "symbol": p.symbol,
                "side": p.side,
                "lots": p.lots,
            }
            for p in server_positions
        }

        engine = ReconciliationEngine()
        result = engine.reconcile(
            account_id=str(account_id),
            server_positions=server_pos_map,
            broker_positions=broker_positions,
        )

        if result.has_critical_discrepancy:
            logger.critical(
                "execution.reconciliation_failure",
                account_id=str(account_id),
                discrepancies=[d.discrepancy_type for d in result.discrepancies],
            )
            await record_audit_event(
                session=session,
                event_type="RECONCILIATION_MISMATCH",
                account_id=account_id,
                payload={
                    "matched_count": result.matched_count,
                    "discrepancies": [
                        {
                            "ticket": d.broker_ticket,
                            "type": d.discrepancy_type,
                            "detail": d.detail,
                        }
                        for d in result.discrepancies
                    ],
                },
            )
            await session.commit()

        return result




async def record_agent_execution_result(
    session: AsyncSession,
    account_id: uuid.UUID,
    command: Any,
    result: dict[str, Any] | None,
    error_message: str | None = None,
) -> None:
    """
    Persist execution outcomes and synchronize Position records.
    Invoked when MT5 EA returns a ResultMessage for OPEN_POSITION or CLOSE_POSITION.
    """
    cmd_type = getattr(command, "command_type", "")
    if cmd_type not in {"OPEN_POSITION", "CLOSE_POSITION"}:
        return

    is_completed = (getattr(command, "status", "") == "COMPLETED")
    res_dict = result or {}

    broker_ticket = res_dict.get("position_ticket") or res_dict.get("order_ticket")
    if broker_ticket is not None:
        try:
            broker_ticket = int(broker_ticket)
        except (ValueError, TypeError):
            broker_ticket = None

    deal_ticket = res_dict.get("deal_ticket")
    if deal_ticket is not None:
        try:
            deal_ticket = int(deal_ticket)
        except (ValueError, TypeError):
            deal_ticket = None

    fill_price = None
    if res_dict.get("executed_price") is not None:
        try:
            fill_price = Decimal(str(res_dict["executed_price"]))
        except Exception:
            fill_price = None

    fill_volume = None
    if res_dict.get("executed_volume") is not None:
        try:
            fill_volume = Decimal(str(res_dict["executed_volume"]))
        except Exception:
            fill_volume = None

    retcode = res_dict.get("retcode")
    if retcode is not None:
        try:
            retcode = int(retcode)
        except (ValueError, TypeError):
            retcode = None

    # 1. Create DbExecutionReport
    db_report = DbExecutionReport(
        id=uuid.uuid4(),
        account_id=account_id,
        command_id=None,
        status="FILLED" if is_completed else "FAILED",
        broker_ticket=broker_ticket,
        fill_price=fill_price,
        fill_volume_lots=fill_volume,
        commission_usd=Decimal("0.00"),
        swap_usd=Decimal("0.00"),
        broker_deal_id=deal_ticket,
        broker_error_code=retcode,
        broker_error_message=error_message or res_dict.get("retcode_description"),
        raw_broker_response_json=json.dumps(res_dict, default=str),
        executed_at=datetime.now(UTC),
    )
    session.add(db_report)

    # 2. Synchronize DbPosition
    if is_completed and cmd_type == "OPEN_POSITION" and broker_ticket:
        existing_stmt = select(DbPosition).where(
            DbPosition.account_id == account_id,
            DbPosition.broker_ticket == broker_ticket,
        )
        res = await session.execute(existing_stmt)
        pos = res.scalar_one_or_none()
        if pos is None:
            side = res_dict.get("side", "BUY")
            pos = DbPosition(
                id=uuid.uuid4(),
                account_id=account_id,
                command_id=None,
                broker_ticket=broker_ticket,
                symbol=res_dict.get("symbol", "XAUUSD"),
                side=side,
                lots=fill_volume or Decimal("0.01"),
                open_price=fill_price or Decimal("0.00"),
                stop_loss=None,
                take_profit=None,
                current_price=fill_price,
                unrealized_pnl_usd=Decimal("0.00"),
                commission_usd=Decimal("0.00"),
                swap_usd=Decimal("0.00"),
                status="OPEN",
                opened_at=datetime.now(UTC),
            )
            session.add(pos)

    elif is_completed and cmd_type == "CLOSE_POSITION":
        target_ticket = broker_ticket
        if not target_ticket and getattr(command, "payload_json", None):
            try:
                payload_data = json.loads(command.payload_json)
                target_ticket = payload_data.get("position_ticket")
            except Exception:
                target_ticket = None

        if target_ticket:
            pos_stmt = select(DbPosition).where(
                DbPosition.account_id == account_id,
                DbPosition.broker_ticket == int(target_ticket),
                DbPosition.status == "OPEN",
            )
            res = await session.execute(pos_stmt)
            pos = res.scalar_one_or_none()
            if pos:
                pos.status = "CLOSED"
                pos.closed_at = datetime.now(UTC)
                if fill_price:
                    pos.close_price = fill_price

        return result
