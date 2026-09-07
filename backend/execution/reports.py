"""
MT5 execution report schemas — TASK-302 / TASK-303.

Defines structured schemas for broker execution results, account state
snapshots, and position/order reports received from the MT5 EA or simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal


class ExecutionStatus(StrEnum):
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class AccountStateReport:
    """Account financial state as reported by MT5 EA — TASK-302."""
    account_id: str
    agent_id: str
    balance_broker: Decimal
    equity_broker: Decimal
    margin_broker: Decimal
    free_margin_broker: Decimal
    floating_pnl_broker: Decimal
    open_positions: int
    reported_at: datetime


@dataclass(frozen=True)
class PositionReport:
    """Position data as reported by MT5 EA — TASK-303."""
    account_id: str
    broker_ticket: int
    symbol: str
    side: Literal["BUY", "SELL"]
    lots: Decimal
    open_price: Decimal
    current_price: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    unrealized_pnl_broker: Decimal
    commission_broker: Decimal
    swap_broker: Decimal
    magic_number: int
    reported_at: datetime


@dataclass(frozen=True)
class ExecutionReport:
    """Broker fill/rejection outcome reported by MT5 EA or Simulator."""
    command_id: str
    account_id: str
    report_id: str = ""
    correlation_id: str = ""
    status: str = "FILLED"
    broker_ticket: int | None = None
    broker_deal_id: int | None = None
    fill_price: Decimal | None = None
    filled_volume_lots: Decimal | None = None
    slippage_points: int | None = 0
    commission_usd: Decimal | None = None
    swap_usd: Decimal | None = None
    broker_error_code: int | None = None
    broker_error_message: str | None = None
    reported_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_simulated: bool = False
    raw_broker_response: dict[str, Any] | None = None

    def __init__(
        self,
        command_id: str,
        account_id: str,
        report_id: str = "",
        correlation_id: str = "",
        status: str = "FILLED",
        broker_ticket: int | None = None,
        broker_deal_id: int | None = None,
        fill_price: Decimal | None = None,
        filled_volume_lots: Decimal | None = None,
        fill_volume_lots: Decimal | None = None,
        slippage_points: int | None = 0,
        commission_usd: Decimal | None = None,
        commission_broker: Decimal | None = None,
        swap_usd: Decimal | None = None,
        swap_broker: Decimal | None = None,
        broker_error_code: int | None = None,
        broker_error_message: str | None = None,
        reported_at: datetime | None = None,
        executed_at: datetime | None = None,
        is_simulated: bool = False,
        raw_broker_response: dict[str, Any] | None = None,
    ) -> None:
        object.__setattr__(self, "command_id", command_id)
        object.__setattr__(self, "account_id", account_id)
        object.__setattr__(self, "report_id", report_id)
        object.__setattr__(self, "correlation_id", correlation_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "broker_ticket", broker_ticket)
        object.__setattr__(self, "broker_deal_id", broker_deal_id)
        object.__setattr__(self, "fill_price", fill_price)
        object.__setattr__(
            self,
            "filled_volume_lots",
            filled_volume_lots if filled_volume_lots is not None else fill_volume_lots,
        )
        object.__setattr__(self, "slippage_points", slippage_points)
        object.__setattr__(
            self,
            "commission_usd",
            commission_usd if commission_usd is not None else commission_broker,
        )
        object.__setattr__(
            self,
            "swap_usd",
            swap_usd if swap_usd is not None else swap_broker,
        )
        object.__setattr__(self, "broker_error_code", broker_error_code)
        object.__setattr__(self, "broker_error_message", broker_error_message)
        object.__setattr__(
            self,
            "reported_at",
            reported_at or executed_at or datetime.now(UTC),
        )
        object.__setattr__(self, "is_simulated", is_simulated)
        object.__setattr__(self, "raw_broker_response", raw_broker_response)

    @property
    def fill_volume_lots(self) -> Decimal | None:
        return self.filled_volume_lots

    @property
    def executed_at(self) -> datetime:
        return self.reported_at

    @property
    def commission_broker(self) -> Decimal | None:
        return self.commission_usd

    @property
    def swap_broker(self) -> Decimal | None:
        return self.swap_usd

    @property
    def is_filled(self) -> bool:
        return self.status == "FILLED"

    @property
    def filled_lots(self) -> Decimal | None:
        return self.filled_volume_lots


