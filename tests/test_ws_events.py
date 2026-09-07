"""
Unit tests for WebSocket event schemas.

Verifies event structure, payload validation, and schema integrity.
No live WebSocket connections required — pure schema tests.
"""

from __future__ import annotations

import json

import pytest

from backend.ws.events import (
    WsEvent,
    make_mt5_connected_event,
    make_mt5_disconnected_event,
    make_risk_state_changed_event,
    make_system_alert_event,
)


@pytest.mark.unit
class TestWsEventSchema:
    def test_event_has_required_fields(self) -> None:
        event = WsEvent(
            event="SYSTEM_ALERT",
            payload={"message": "test"},
        )
        assert event.event == "SYSTEM_ALERT"
        assert event.version == 1
        assert event.timestamp is not None
        assert event.correlation_id is not None
        assert isinstance(event.payload, dict)

    def test_event_is_json_serializable(self) -> None:
        event = WsEvent(event="SYSTEM_ALERT", payload={"msg": "hello"})
        serialized = event.model_dump_json()
        parsed = json.loads(serialized)
        assert parsed["event"] == "SYSTEM_ALERT"
        assert parsed["version"] == 1

    def test_correlation_id_auto_generated(self) -> None:
        e1 = WsEvent(event="SYSTEM_ALERT", payload={})
        e2 = WsEvent(event="SYSTEM_ALERT", payload={})
        assert e1.correlation_id != e2.correlation_id

    def test_account_id_optional(self) -> None:
        event = WsEvent(event="SYSTEM_ALERT", payload={})
        assert event.account_id is None


@pytest.mark.unit
class TestEventConstructors:
    def test_risk_state_changed_event(self) -> None:
        event = make_risk_state_changed_event(
            account_id="acc-001",
            state="NOT_CONFIGURED",
            trading_allowed=False,
            block_reason="Risk parameters UNDEFINED",
        )
        assert event.event == "RISK_STATE_CHANGED"
        assert event.account_id == "acc-001"
        assert event.payload["state"] == "NOT_CONFIGURED"
        assert event.payload["trading_allowed"] is False
        assert event.payload["block_reason"] == "Risk parameters UNDEFINED"

    def test_mt5_connected_event(self) -> None:
        event = make_mt5_connected_event(
            account_id="acc-001",
            agent_id="agent-xyz",
            mt5_version="5.0.37",
        )
        assert event.event == "MT5_CONNECTED"
        assert event.payload["agent_id"] == "agent-xyz"

    def test_mt5_disconnected_event(self) -> None:
        event = make_mt5_disconnected_event(
            account_id="acc-001",
            agent_id="agent-xyz",
            reason="Connection timeout",
        )
        assert event.event == "MT5_DISCONNECTED"
        assert event.payload["reason"] == "Connection timeout"

    def test_system_alert_event_defaults(self) -> None:
        event = make_system_alert_event(message="Database unreachable")
        assert event.event == "SYSTEM_ALERT"
        assert event.payload["severity"] == "WARNING"
        assert event.account_id is None
