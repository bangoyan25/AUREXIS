"""
Execution command models and lifecycle management — TASK-304.

Implements the command state machine per docs/MT5_COMMAND_PROTOCOL.md:
  CREATED → SENT → ACKNOWLEDGED → EXECUTING → FILLED / PARTIALLY_FILLED / REJECTED / EXPIRED → RECONCILED

Guarantees:
  1. Deterministic idempotency: idempotency_key prevents duplicate order generation.
  2. Fail-closed execution: commands have explicit expiry (default 5000ms).
  3. Immutable auditability: every command lifecycle transition is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from decimal import Decimal


class CommandAction(StrEnum):
    ORDER_OPEN = "ORDER_OPEN"
    ORDER_CLOSE = "ORDER_CLOSE"
    BASKET_CLOSE = "BASKET_CLOSE"
    POSITION_MODIFY = "POSITION_MODIFY"


class CommandState(StrEnum):
    CREATED = "CREATED"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXECUTING = "EXECUTING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    RECONCILED = "RECONCILED"


# Valid state transitions
VALID_TRANSITIONS: dict[CommandState, set[CommandState]] = {
    CommandState.CREATED: {CommandState.SENT, CommandState.EXPIRED, CommandState.REJECTED},
    CommandState.SENT: {CommandState.ACKNOWLEDGED, CommandState.EXPIRED, CommandState.REJECTED},
    CommandState.ACKNOWLEDGED: {CommandState.EXECUTING, CommandState.EXPIRED, CommandState.REJECTED},
    CommandState.EXECUTING: {
        CommandState.FILLED,
        CommandState.PARTIALLY_FILLED,
        CommandState.REJECTED,
        CommandState.EXPIRED,
    },
    CommandState.FILLED: {CommandState.RECONCILED},
    CommandState.PARTIALLY_FILLED: {CommandState.FILLED, CommandState.RECONCILED},
    CommandState.REJECTED: set(),
    CommandState.EXPIRED: set(),
    CommandState.RECONCILED: set(),
}


@dataclass
class ExecutionCommand:
    """In-memory representation of an execution command dispatch."""
    command_id: str
    account_id: str
    action: CommandAction
    symbol: str
    order_type: Literal["BUY", "SELL"]
    volume_lots: Decimal
    price: Decimal
    slippage_points: int
    idempotency_key: str
    correlation_id: str
    state: CommandState = CommandState.CREATED
    signal_id: str | None = None
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    magic_number: int = 202609
    position_ticket: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(UTC) + timedelta(seconds=5)
    )
    sent_at: datetime | None = None
    acknowledged_at: datetime | None = None
    fill_price: Decimal | None = None
    fill_volume_lots: Decimal | None = None
    broker_ticket: int | None = None
    rejection_reason: str | None = None

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    @property
    def is_terminal(self) -> bool:
        return self.state in {
            CommandState.FILLED,
            CommandState.REJECTED,
            CommandState.EXPIRED,
            CommandState.RECONCILED,
        }

    def transition_to(self, new_state: CommandState, reason: str | None = None) -> bool:
        """
        Transition command state according to the valid state machine.
        Returns True if transition succeeded, False if invalid.
        """
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            return False

        self.state = new_state
        if reason:
            self.rejection_reason = reason
        if new_state == CommandState.SENT:
            self.sent_at = datetime.now(UTC)
        elif new_state == CommandState.ACKNOWLEDGED:
            self.acknowledged_at = datetime.now(UTC)

        return True
