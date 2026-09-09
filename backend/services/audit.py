"""
Audit log service.

Provides a clean interface for recording immutable audit events.
Direct model usage is discouraged — always go through this service
to ensure consistent payload structure and timestamp handling.

Audit records are append-only. No UPDATE or DELETE operations are performed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger
from backend.db.models.audit_log import AuditLog

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("audit")


class AuditEventType:
    """Canonical event type constants — use these, not raw strings."""
    # Authentication
    USER_LOGIN = "USER_LOGIN"
    USER_LOGIN_FAILED = "USER_LOGIN_FAILED"
    USER_LOGOUT = "USER_LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    REFRESH_TOKEN_REVOKED = "REFRESH_TOKEN_REVOKED"

    # Account management
    ACCOUNT_CREATED = "ACCOUNT_CREATED"
    ACCOUNT_UPDATED = "ACCOUNT_UPDATED"
    ACCOUNT_DELETED = "ACCOUNT_DELETED"
    TRADING_ENABLED = "TRADING_ENABLED"
    TRADING_DISABLED = "TRADING_DISABLED"

    # MT5 connectivity
    MT5_AGENT_CONNECTED = "MT5_AGENT_CONNECTED"
    MT5_AGENT_DISCONNECTED = "MT5_AGENT_DISCONNECTED"
    MT5_AGENT_REGISTERED = "MT5_AGENT_REGISTERED"
    MT5_AGENT_COMMAND_CREATED = "MT5_AGENT_COMMAND_CREATED"
    MT5_AGENT_COMMAND_SENT = "MT5_AGENT_COMMAND_SENT"
    MT5_AGENT_COMMAND_ACKNOWLEDGED = "MT5_AGENT_COMMAND_ACKNOWLEDGED"
    MT5_AGENT_COMMAND_COMPLETED = "MT5_AGENT_COMMAND_COMPLETED"
    MT5_AGENT_COMMAND_FAILED = "MT5_AGENT_COMMAND_FAILED"
    MT5_AGENT_COMMAND_DELIVERED = "MT5_AGENT_COMMAND_DELIVERED"  # WS delivery confirmed

    # Risk
    RISK_STATE_CHANGED = "RISK_STATE_CHANGED"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    EMERGENCY_STOP_CLEARED = "EMERGENCY_STOP_CLEARED"

    # Trading pipeline
    SIGNAL_CREATED = "SIGNAL_CREATED"
    SIGNAL_BLOCKED = "SIGNAL_BLOCKED"
    COMMAND_CREATED = "COMMAND_CREATED"
    COMMAND_APPROVED = "COMMAND_APPROVED"
    COMMAND_REJECTED = "COMMAND_REJECTED"
    EXECUTION_RESULT = "EXECUTION_RESULT"

    # Reconciliation
    RECONCILIATION_OK = "RECONCILIATION_OK"
    RECONCILIATION_MISMATCH = "RECONCILIATION_MISMATCH"

    # Configuration
    CONFIG_CHANGED = "CONFIG_CHANGED"
    SYSTEM_ALERT = "SYSTEM_ALERT"


class Severity:
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


async def record_audit_event(
    session: AsyncSession,
    event_type: str,
    *,
    severity: str = Severity.INFO,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    mt5_agent_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """
    Record an immutable audit event.

    This function is the single point of entry for all audit logging.
    It ensures consistent timestamp (UTC), payload serialization, and logging.

    The returned AuditLog instance is added to the session but NOT committed —
    the caller is responsible for committing as part of their transaction.
    """
    payload_json: str | None = None
    if payload is not None:
        try:
            payload_json = json.dumps(payload, default=str)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "audit.payload_serialization_failed",
                event_type=event_type,
                error=str(exc),
            )
            payload_json = json.dumps({"_serialization_error": str(exc)})

    entry = AuditLog(
        event_type=event_type,
        severity=severity,
        user_id=user_id,
        account_id=account_id,
        mt5_agent_id=mt5_agent_id,
        payload_json=payload_json,
        correlation_id=correlation_id,
        ip_address=ip_address,
        occurred_at=datetime.now(UTC),
    )
    session.add(entry)

    logger.info(
        "audit.event",
        event_type=event_type,
        severity=severity,
        user_id=str(user_id) if user_id else None,
        account_id=str(account_id) if account_id else None,
        correlation_id=correlation_id,
    )

    return entry
