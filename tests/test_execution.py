"""
Tests for Phase 3 MT5 execution models, commands, and reconciliation.

TASK-301 through TASK-305 acceptance criteria.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from backend.execution.commands import CommandAction, CommandState, ExecutionCommand
from backend.execution.reconciliation import ReconciliationEngine
from backend.execution.reports import AccountStateReport, ExecutionReport, PositionReport


class TestExecutionCommandLifecycle:
    """TASK-304: Command lifecycle state transitions."""

    def _make_command(self, state: CommandState = CommandState.CREATED) -> ExecutionCommand:
        return ExecutionCommand(
            command_id=str(uuid.uuid4()),
            account_id=str(uuid.uuid4()),
            action=CommandAction.ORDER_OPEN,
            symbol="XAUUSD",
            order_type="BUY",
            volume_lots=Decimal("0.01"),
            price=Decimal("2735.50"),
            slippage_points=20,
            idempotency_key=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            state=state,
        )

    def test_initial_state_is_created(self) -> None:
        cmd = self._make_command()
        assert cmd.state == CommandState.CREATED
        assert not cmd.is_terminal
        assert not cmd.is_expired

    def test_valid_progression_to_filled(self) -> None:
        cmd = self._make_command()
        assert cmd.transition_to(CommandState.SENT)
        assert cmd.sent_at is not None
        assert cmd.transition_to(CommandState.ACKNOWLEDGED)
        assert cmd.acknowledged_at is not None
        assert cmd.transition_to(CommandState.EXECUTING)
        assert cmd.transition_to(CommandState.FILLED)
        assert cmd.is_terminal

    def test_invalid_transition_rejected(self) -> None:
        cmd = self._make_command(state=CommandState.CREATED)
        assert not cmd.transition_to(CommandState.FILLED)
        assert cmd.state == CommandState.CREATED

    def test_terminal_state_cannot_transition(self) -> None:
        cmd = self._make_command(state=CommandState.REJECTED)
        assert cmd.is_terminal
        assert not cmd.transition_to(CommandState.SENT)
        assert not cmd.transition_to(CommandState.FILLED)

    def test_expiration_check(self) -> None:
        cmd = self._make_command()
        cmd.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        assert cmd.is_expired

    def test_rejection_reason_recorded(self) -> None:
        cmd = self._make_command(state=CommandState.EXECUTING)
        reason = "BROKER_REJECT_INSUFFICIENT_MARGIN"
        assert cmd.transition_to(CommandState.REJECTED, reason=reason)
        assert cmd.rejection_reason == reason


class TestReconciliationEngine:
    """TASK-305: Reconciliation engine discrepancy detection."""

    def setup_method(self) -> None:
        self.engine = ReconciliationEngine()
        self.account_id = str(uuid.uuid4())

    def test_clean_state_when_positions_match(self) -> None:
        ticket = 1001
        server_positions = {
            ticket: {
                "lots": Decimal("0.01"),
                "side": "BUY",
                "symbol": "XAUUSD",
                "status": "OPEN",
            }
        }
        broker_positions = [
            PositionReport(
                account_id=self.account_id,
                broker_ticket=ticket,
                symbol="XAUUSD",
                side="BUY",
                lots=Decimal("0.01"),
                open_price=Decimal("2735.00"),
                current_price=Decimal("2738.00"),
                stop_loss=None,
                take_profit=None,
                unrealized_pnl_broker=Decimal("3.00"),
                commission_broker=Decimal("0.05"),
                swap_broker=Decimal("0.00"),
                magic_number=202609,
                reported_at=datetime.now(UTC),
            )
        ]

        result = self.engine.reconcile(self.account_id, server_positions, broker_positions)
        assert result.is_clean
        assert result.matched_count == 1
        assert len(result.discrepancies) == 0
        assert not result.has_critical_discrepancy

    def test_orphan_detected(self) -> None:
        ticket = 9999
        server_positions: dict[int, dict[str, object]] = {}
        broker_positions = [
            PositionReport(
                account_id=self.account_id,
                broker_ticket=ticket,
                symbol="XAUUSD",
                side="SELL",
                lots=Decimal("0.02"),
                open_price=Decimal("2740.00"),
                current_price=Decimal("2735.00"),
                stop_loss=None,
                take_profit=None,
                unrealized_pnl_broker=Decimal("10.00"),
                commission_broker=Decimal("0.10"),
                swap_broker=Decimal("0.00"),
                magic_number=202609,
                reported_at=datetime.now(UTC),
            )
        ]

        result = self.engine.reconcile(self.account_id, server_positions, broker_positions)
        assert not result.is_clean
        assert len(result.discrepancies) == 1
        assert result.discrepancies[0].discrepancy_type == "ORPHAN"
        assert result.has_critical_discrepancy

    def test_phantom_detected(self) -> None:
        ticket = 2002
        server_positions = {
            ticket: {
                "lots": Decimal("0.01"),
                "side": "BUY",
                "symbol": "XAUUSD",
                "status": "OPEN",
            }
        }
        broker_positions: list[PositionReport] = []

        result = self.engine.reconcile(self.account_id, server_positions, broker_positions)
        assert not result.is_clean
        assert len(result.discrepancies) == 1
        assert result.discrepancies[0].discrepancy_type == "PHANTOM"

    def test_volume_mismatch_detected(self) -> None:
        ticket = 3003
        server_positions = {
            ticket: {
                "lots": Decimal("0.01"),
                "side": "BUY",
                "symbol": "XAUUSD",
                "status": "OPEN",
            }
        }
        broker_positions = [
            PositionReport(
                account_id=self.account_id,
                broker_ticket=ticket,
                symbol="XAUUSD",
                side="BUY",
                lots=Decimal("0.05"),
                open_price=Decimal("2735.00"),
                current_price=Decimal("2738.00"),
                stop_loss=None,
                take_profit=None,
                unrealized_pnl_broker=Decimal("15.00"),
                commission_broker=Decimal("0.25"),
                swap_broker=Decimal("0.00"),
                magic_number=202609,
                reported_at=datetime.now(UTC),
            )
        ]

        result = self.engine.reconcile(self.account_id, server_positions, broker_positions)
        assert not result.is_clean
        assert result.discrepancies[0].discrepancy_type == "VOLUME_MISMATCH"
        assert result.has_critical_discrepancy


class TestReportSchemas:
    """TASK-302 / TASK-303: Report schemas initialization."""

    def test_account_state_report_types(self) -> None:
        rpt = AccountStateReport(
            account_id=str(uuid.uuid4()),
            agent_id=str(uuid.uuid4()),
            balance_broker=Decimal("10000.00"),
            equity_broker=Decimal("10050.00"),
            margin_broker=Decimal("150.00"),
            free_margin_broker=Decimal("9900.00"),
            floating_pnl_broker=Decimal("50.00"),
            open_positions=1,
            reported_at=datetime.now(UTC),
        )
        assert isinstance(rpt.balance_broker, Decimal)
        assert rpt.open_positions == 1

    def test_execution_report_types(self) -> None:
        rpt = ExecutionReport(
            command_id=str(uuid.uuid4()),
            account_id=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            status="FILLED",
            broker_ticket=89412051,
            broker_deal_id=7410294,
            fill_price=Decimal("2735.50"),
            fill_volume_lots=Decimal("0.01"),
            slippage_points=5,
            commission_broker=Decimal("0.05"),
            swap_broker=Decimal("0.00"),
            broker_error_code=None,
            broker_error_message=None,
            executed_at=datetime.now(UTC),
        )
        assert rpt.status == "FILLED"
        assert rpt.broker_ticket == 89412051

