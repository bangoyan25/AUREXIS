"""
MT5 Agent Simulator — Local development and paper execution testing.

Provides a deterministic mock of the MT5 EA:
- Acknowledges received commands
- Fills market orders at current simulated price
- Rejects commands that are expired or invalid
- Reports simulated broker tickets and execution reports
- Clearly labels all output with is_simulated = True
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from backend.core.logging import get_logger
from backend.execution.commands import CommandAction, ExecutionCommand
from backend.execution.reports import ExecutionReport, ExecutionStatus, PositionReport

logger = get_logger("execution.simulator")


class MT5AgentSimulator:
    """
    Deterministic MT5 EA Simulator for local-first testing without live broker.

    Maintains in-memory simulated broker position state so that reconciliation
    can compare server DB positions against simulator open positions.
    All fills are explicitly marked is_simulated = True.
    """

    MODE: str = "SIMULATION"

    def __init__(self, simulated_bid: Decimal = Decimal("2000.00"), simulated_ask: Decimal = Decimal("2000.20")) -> None:
        self.simulated_bid = simulated_bid
        self.simulated_ask = simulated_ask
        self._ticket_counter = 1000000
        self._positions: dict[int, PositionReport] = {}

    def _next_ticket(self) -> int:
        self._ticket_counter += 1
        return self._ticket_counter

    def get_open_positions(self) -> list[PositionReport]:
        """Return currently open simulated broker positions."""
        return list(self._positions.values())

    def execute_command(self, command: ExecutionCommand, current_market_price: Decimal | None = None) -> ExecutionReport:
        """Simulate execution of an authorized ExecutionCommand."""
        now = datetime.now(UTC)

        # Check expiration
        if command.is_expired:
            logger.info("simulator.command_expired", command_id=str(command.command_id))
            return ExecutionReport(
                report_id=f"rep_{command.command_id}",
                command_id=command.command_id,
                account_id=command.account_id,
                broker_ticket=None,
                status=ExecutionStatus.EXPIRED,
                filled_volume_lots=None,
                fill_price=None,
                slippage_points=0,
                reported_at=now,
                is_simulated=True,
                raw_broker_response={"error": "COMMAND_EXPIRED_IN_SIMULATOR"},
            )

        # Action handling
        if command.action in (CommandAction.ORDER_OPEN,):
            default_p = self.simulated_ask if command.order_type == "BUY" else self.simulated_bid
            fill_price = current_market_price or default_p
            ticket = self._next_ticket()

            pos = PositionReport(
                account_id=command.account_id,
                broker_ticket=ticket,
                symbol=command.symbol,
                side=command.order_type,
                lots=command.volume_lots,
                open_price=fill_price,
                current_price=fill_price,
                stop_loss=command.stop_loss,
                take_profit=command.take_profit,
                unrealized_pnl_broker=Decimal("0.00"),
                commission_broker=Decimal("0.00"),
                swap_broker=Decimal("0.00"),
                magic_number=command.magic_number,
                reported_at=now,
            )
            self._positions[ticket] = pos

            return ExecutionReport(
                report_id=f"rep_{command.command_id}",
                command_id=command.command_id,
                account_id=command.account_id,
                broker_ticket=ticket,
                status=ExecutionStatus.FILLED,
                filled_volume_lots=command.volume_lots,
                fill_price=fill_price,
                slippage_points=0,
                commission_usd=Decimal("0.00"),
                swap_usd=Decimal("0.00"),
                reported_at=now,
                is_simulated=True,
                raw_broker_response={"retcode": 10009, "comment": "Simulated fill OK", "ticket": ticket},
            )
        elif command.action in (CommandAction.ORDER_CLOSE, CommandAction.BASKET_CLOSE):
            target_ticket = command.position_ticket
            if target_ticket and target_ticket in self._positions:
                del self._positions[target_ticket]

            return ExecutionReport(
                report_id=f"rep_{command.command_id}",
                command_id=command.command_id,
                account_id=command.account_id,
                broker_ticket=command.position_ticket,
                status=ExecutionStatus.FILLED,
                filled_volume_lots=command.volume_lots,
                fill_price=current_market_price or self.simulated_bid,
                slippage_points=0,
                reported_at=now,
                is_simulated=True,
                raw_broker_response={"retcode": 10009, "comment": "Simulated close OK"},
            )
        else:
            return ExecutionReport(
                report_id=f"rep_{command.command_id}",
                command_id=command.command_id,
                account_id=command.account_id,
                broker_ticket=None,
                status=ExecutionStatus.REJECTED,
                filled_volume_lots=None,
                fill_price=None,
                slippage_points=0,
                reported_at=now,
                is_simulated=True,
                raw_broker_response={"error": f"UNSUPPORTED_ACTION:{command.action}"},
            )
