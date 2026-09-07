"""
Deterministic MT5 Agent Simulator for Local Testing and Development.

Explicitly marked as SIMULATION — never communicates with live broker.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from backend.execution.commands import CommandAction, ExecutionCommand
from backend.execution.reports import AccountStateReport, ExecutionReport, PositionReport


class MT5AgentSimulator:
    """
    Simulates MT5 EA behavior locally for automated testing and simulation mode.
    Maintains local virtual broker state.
    """

    def __init__(
        self,
        account_id: str,
        agent_id: str = "sim-agent-001",
        initial_balance_usd: Decimal = Decimal("10000.00"),
    ) -> None:
        self.account_id = account_id
        self.agent_id = agent_id
        self.balance = initial_balance_usd
        self.equity = initial_balance_usd
        self.mode: Literal["SIMULATION"] = "SIMULATION"
        self._positions: dict[int, PositionReport] = {}
        self._ticket_counter = 800001

    def process_command(
        self,
        command: ExecutionCommand,
        current_market_price: Decimal | None = None,
    ) -> ExecutionReport:
        """Process an execution command and return a simulated ExecutionReport."""
        if command.is_expired:
            return ExecutionReport(
                command_id=command.command_id,
                account_id=self.account_id,
                status="EXPIRED",
                is_simulated=True,
                broker_error_message="Command expired before execution",
            )

        exec_price = current_market_price or command.price
        ticket = self._ticket_counter
        self._ticket_counter += 1

        if command.action in (CommandAction.ORDER_OPEN, "OPEN_BUY", "OPEN_SELL"):
            side: Literal["BUY", "SELL"] = "BUY" if "BUY" in str(command.action).upper() or command.order_type == "BUY" else "SELL"
            pos = PositionReport(
                account_id=self.account_id,
                broker_ticket=ticket,
                symbol=command.symbol,
                side=side,
                lots=command.volume_lots,
                open_price=exec_price,
                current_price=exec_price,
                stop_loss=command.stop_loss,
                take_profit=command.take_profit,
                unrealized_pnl_broker=Decimal("0.00"),
                commission_broker=Decimal("0.05"),
                swap_broker=Decimal("0.00"),
                magic_number=command.magic_number,
                reported_at=datetime.now(UTC),
            )
            self._positions[ticket] = pos

            return ExecutionReport(
                command_id=command.command_id,
                account_id=self.account_id,
                report_id=str(uuid.uuid4()),
                correlation_id=command.correlation_id,
                status="FILLED",
                broker_ticket=ticket,
                fill_price=exec_price,
                filled_volume_lots=command.volume_lots,
                slippage_points=0,
                commission_usd=Decimal("0.05"),
                swap_usd=Decimal("0.00"),
                is_simulated=True,
            )

        elif command.action in (CommandAction.ORDER_CLOSE, "CLOSE"):
            target_ticket = command.position_ticket
            if target_ticket and target_ticket in self._positions:
                del self._positions[target_ticket]

            return ExecutionReport(
                command_id=command.command_id,
                account_id=self.account_id,
                report_id=str(uuid.uuid4()),
                correlation_id=command.correlation_id,
                status="FILLED",
                broker_ticket=target_ticket,
                fill_price=exec_price,
                filled_volume_lots=command.volume_lots,
                is_simulated=True,
            )

        return ExecutionReport(
            command_id=command.command_id,
            account_id=self.account_id,
            status="REJECTED",
            is_simulated=True,
            broker_error_message=f"Unsupported simulated action: {command.action}",
        )

    def get_open_positions(self) -> list[PositionReport]:
        """Return currently open virtual broker positions."""
        return list(self._positions.values())

    def get_account_state(self) -> AccountStateReport:
        """Return simulated account state snapshot."""
        return AccountStateReport(
            account_id=self.account_id,
            agent_id=self.agent_id,
            balance_broker=self.balance,
            equity_broker=self.equity,
            margin_broker=Decimal("0.00"),
            free_margin_broker=self.equity,
            floating_pnl_broker=Decimal("0.00"),
            open_positions=len(self._positions),
            reported_at=datetime.now(UTC),
        )

    def send_heartbeat(self) -> dict[str, Any]:
        """Generate a simulated agent heartbeat payload."""
        return {
            "agent_id": self.agent_id,
            "account_id": self.account_id,
            "status": "CONNECTED",
            "mode": "SIMULATION",
            "timestamp": datetime.now(UTC).isoformat(),
            "open_positions": len(self._positions),
        }
