"""
Agent WebSocket protocol schemas.

Defines all allowed message types for the agent ↔ backend bidirectional channel.
Only explicitly listed types are accepted; unknown types are rejected with a
structured protocol error.

Agent → Server messages:
  hello     — capability handshake on connect
  heartbeat — periodic keepalive with status
  ack       — acknowledge receipt of a command
  result    — submit final result or failure for a command

Server → Agent messages:
  welcome         — server acknowledgement of hello
  heartbeat_ack   — server acknowledgement of heartbeat
  command         — deliver a pending command to the agent
  error           — structured protocol or auth error
"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Agent → Server
# ---------------------------------------------------------------------------


class HelloMessage(BaseModel):
    """Sent by agent immediately after connection is established."""

    type: Literal["hello"]
    agent_version: str | None = Field(default=None, max_length=50)
    mt5_version: str | None = Field(default=None, max_length=50)
    ea_version: str | None = Field(default=None, max_length=50)
    capabilities: list[str] = Field(default_factory=list)

    @field_validator("capabilities")
    @classmethod
    def cap_max_length(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("Too many capabilities")
        return [c.upper() for c in v]


class HeartbeatMessage(BaseModel):
    """Periodic keepalive sent from agent to server."""

    type: Literal["heartbeat"]
    status: str = Field(default="CONNECTED", max_length=50)
    mt5_version: str | None = Field(default=None, max_length=50)
    ea_version: str | None = Field(default=None, max_length=50)


class AckMessage(BaseModel):
    """Agent acknowledges receipt of a delivered command."""

    type: Literal["ack"]
    command_id: str = Field(min_length=1, max_length=36)

    @field_validator("command_id")
    @classmethod
    def valid_uuid(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError as exc:
            raise ValueError("command_id must be a valid UUID") from exc
        return v


class ResultMessage(BaseModel):
    """Agent reports final outcome of a command."""

    type: Literal["result"]
    command_id: str = Field(min_length=1, max_length=36)
    status: str = Field(description="COMPLETED or FAILED", max_length=20)
    result: dict[str, Any] | None = None
    error_message: str | None = Field(default=None, max_length=500)

    @field_validator("command_id")
    @classmethod
    def valid_uuid(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError as exc:
            raise ValueError("command_id must be a valid UUID") from exc
        return v

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        upper = v.upper()
        if upper not in {"COMPLETED", "FAILED"}:
            raise ValueError("status must be COMPLETED or FAILED")
        return upper


class MarketDataMessage(BaseModel):
    """Real-time market tick from MT5 execution agent."""

    type: Literal["market_data"]
    symbol: str = Field(min_length=1, max_length=20)
    bid: Decimal
    ask: Decimal
    spread: Decimal
    point: Decimal = Field(default=Decimal("0.01"))
    digits: int = Field(default=2, ge=0, le=8)
    tick_time: str = Field(min_length=1, max_length=50)
    tick_volume: int | float | None = Field(default=0)
    timestamp: str | None = Field(default=None, max_length=50)

    @field_validator("symbol")
    @classmethod
    def clean_symbol(cls, v: str) -> str:
        s = v.strip().upper()
        if not s:
            raise ValueError("symbol cannot be empty")
        return s

    @field_validator("bid", "ask", "spread", "point", mode="before")
    @classmethod
    def parse_and_validate_decimal(cls, v: Any, info: Any) -> Decimal:
        if v is None:
            raise ValueError(f"{info.field_name} cannot be None")
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise ValueError(f"{info.field_name} cannot be NaN or Infinite")
        try:
            d = Decimal(str(v))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"{info.field_name} must be a valid numeric value") from exc

        if d.is_nan() or d.is_infinite():
            raise ValueError(f"{info.field_name} cannot be NaN or Infinite")

        if info.field_name in ("bid", "ask") and d <= Decimal("0"):
            raise ValueError(f"{info.field_name} must be greater than 0")
        if info.field_name in ("spread", "point") and d < Decimal("0"):
            raise ValueError(f"{info.field_name} cannot be negative")
        return d

    @field_validator("tick_volume", mode="before")
    @classmethod
    def validate_tick_volume(cls, v: Any) -> int | float | None:
        if v is None:
            return 0
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise ValueError("tick_volume cannot be NaN or Infinite")
        if isinstance(v, (int, float)) and v < 0:
            raise ValueError("tick_volume cannot be negative")
        return v

    @model_validator(mode="after")
    def validate_bid_ask(self) -> Self:
        if self.ask < self.bid:
            raise ValueError(f"ask ({self.ask}) cannot be less than bid ({self.bid})")
        return self


# ---------------------------------------------------------------------------
# Server → Agent
# ---------------------------------------------------------------------------


class WelcomeMessage(BaseModel):
    """Server acknowledgement of hello handshake."""

    type: Literal["welcome"] = "welcome"
    server_version: str = "1.0"
    # Authoritative command allowlist — do not trust agent-reported capabilities
    allowed_commands: list[str] = Field(
        default_factory=lambda: ["PING", "GET_STATUS", "OPEN_POSITION", "CLOSE_POSITION"]
    )
    message: str = "AUREXIS agent channel established"


class HeartbeatAckMessage(BaseModel):
    """Server acknowledgement of heartbeat."""

    type: Literal["heartbeat_ack"] = "heartbeat_ack"
    status: str = "OK"


class CommandMessage(BaseModel):
    """Server delivers a pending command to the agent."""

    type: Literal["command"] = "command"
    command: CommandPayload


class CommandPayload(BaseModel):
    """Payload nested inside CommandMessage."""

    id: str
    command_type: str
    payload: dict[str, Any] | None = None


class ErrorMessage(BaseModel):
    """Structured protocol error from server."""

    type: Literal["error"] = "error"
    code: str
    message: str


# ---------------------------------------------------------------------------
# Discriminated union helpers
# ---------------------------------------------------------------------------

ALLOWED_AGENT_MESSAGE_TYPES = frozenset({"hello", "heartbeat", "ack", "result", "market_data"})


def parse_agent_message(
    data: dict[str, Any],
) -> HelloMessage | HeartbeatMessage | AckMessage | ResultMessage | MarketDataMessage:
    """
    Parse and validate an incoming agent message dict.

    Raises ValueError with a human-readable message on invalid input.
    Unknown types are rejected before attempting field validation.
    """
    msg_type = data.get("type")
    if msg_type not in ALLOWED_AGENT_MESSAGE_TYPES:
        raise ValueError(
            f"Unknown message type '{msg_type}'. "
            f"Allowed: {sorted(ALLOWED_AGENT_MESSAGE_TYPES)}"
        )

    if msg_type == "hello":
        return HelloMessage(**data)
    if msg_type == "heartbeat":
        return HeartbeatMessage(**data)
    if msg_type == "ack":
        return AckMessage(**data)
    if msg_type == "result":
        return ResultMessage(**data)
    return MarketDataMessage(**data)
