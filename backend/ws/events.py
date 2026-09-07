"""
WebSocket event schemas for AUREXIS.

All events emitted to connected frontend clients must use these schemas.
Payloads are versioned so clients can handle schema evolution.

Event types mirror those defined in frontend/types/domain.ts.
Both must stay in sync.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Event type literals ────────────────────────────────────────────────────

WsEventType = Literal[
    "ACCOUNT_UPDATED",
    "POSITION_UPDATED",
    "TRADE_UPDATED",
    "PNL_UPDATED",
    "SIGNAL_CREATED",
    "COMMAND_CREATED",
    "COMMAND_UPDATED",
    "RISK_STATE_CHANGED",
    "MT5_CONNECTED",
    "MT5_DISCONNECTED",
    "SYSTEM_ALERT",
]


# ── Base event envelope ────────────────────────────────────────────────────

class WsEvent(BaseModel):
    """
    Server-to-client WebSocket event envelope.

    All frontend-bound realtime messages use this structure.
    The `payload` field contains the event-specific data.
    """
    event: WsEventType
    version: Literal[1] = 1
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())
    )
    account_id: str | None = None
    payload: dict[str, Any]

    model_config = {"frozen": True}


# ── Event constructors ─────────────────────────────────────────────────────

def make_risk_state_changed_event(
    account_id: str,
    state: str,
    trading_allowed: bool,
    block_reason: str | None = None,
    correlation_id: str | None = None,
) -> WsEvent:
    return WsEvent(
        event="RISK_STATE_CHANGED",
        account_id=account_id,
        correlation_id=correlation_id or str(uuid.uuid4()),
        payload={
            "state": state,
            "trading_allowed": trading_allowed,
            "block_reason": block_reason,
        },
    )


def make_mt5_connected_event(
    account_id: str,
    agent_id: str,
    mt5_version: str | None = None,
) -> WsEvent:
    return WsEvent(
        event="MT5_CONNECTED",
        account_id=account_id,
        payload={
            "agent_id": agent_id,
            "mt5_version": mt5_version,
        },
    )


def make_mt5_disconnected_event(
    account_id: str,
    agent_id: str,
    reason: str | None = None,
) -> WsEvent:
    return WsEvent(
        event="MT5_DISCONNECTED",
        account_id=account_id,
        payload={
            "agent_id": agent_id,
            "reason": reason,
        },
    )


def make_system_alert_event(
    message: str,
    severity: str = "WARNING",
    account_id: str | None = None,
) -> WsEvent:
    return WsEvent(
        event="SYSTEM_ALERT",
        account_id=account_id,
        payload={
            "message": message,
            "severity": severity,
        },
    )


def make_signal_created_event(
    account_id: str | None,
    signal_id: str,
    symbol: str,
    direction: str,
    regime: str | None = None,
    setup_type: str | None = None,
    confidence_score: str | None = None,
    expires_at: str | None = None,
    correlation_id: str | None = None,
) -> WsEvent:
    return WsEvent(
        event="SIGNAL_CREATED",
        account_id=account_id,
        correlation_id=correlation_id or str(uuid.uuid4()),
        payload={
            "signal_id": signal_id,
            "symbol": symbol,
            "direction": direction,
            "regime": regime,
            "setup_type": setup_type,
            "confidence_score": confidence_score,
            "expires_at": expires_at,
        },
    )


def make_command_created_event(
    account_id: str,
    command_id: str,
    action: str,
    symbol: str,
    order_type: str,
    volume_lots: str,
    price: str | None = None,
    correlation_id: str | None = None,
) -> WsEvent:
    return WsEvent(
        event="COMMAND_CREATED",
        account_id=account_id,
        correlation_id=correlation_id or str(uuid.uuid4()),
        payload={
            "command_id": command_id,
            "action": action,
            "symbol": symbol,
            "order_type": order_type,
            "volume_lots": volume_lots,
            "price": price,
        },
    )


def make_command_updated_event(
    account_id: str,
    command_id: str,
    status: str,
    broker_ticket: int | None = None,
    fill_price: str | None = None,
    fill_volume_lots: str | None = None,
    correlation_id: str | None = None,
) -> WsEvent:
    return WsEvent(
        event="COMMAND_UPDATED",
        account_id=account_id,
        correlation_id=correlation_id or str(uuid.uuid4()),
        payload={
            "command_id": command_id,
            "status": status,
            "broker_ticket": broker_ticket,
            "fill_price": fill_price,
            "fill_volume_lots": fill_volume_lots,
        },
    )


def make_position_updated_event(
    account_id: str,
    broker_ticket: int,
    symbol: str,
    side: str,
    lots: str,
    open_price: str,
    current_price: str | None = None,
    stop_loss: str | None = None,
    take_profit: str | None = None,
    unrealized_pnl_usd: str | None = None,
    status: str = "OPEN",
    correlation_id: str | None = None,
) -> WsEvent:
    return WsEvent(
        event="POSITION_UPDATED",
        account_id=account_id,
        correlation_id=correlation_id or str(uuid.uuid4()),
        payload={
            "broker_ticket": broker_ticket,
            "symbol": symbol,
            "side": side,
            "lots": lots,
            "open_price": open_price,
            "current_price": current_price or open_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "unrealized_pnl_usd": unrealized_pnl_usd or "0.00",
            "status": status,
        },
    )

