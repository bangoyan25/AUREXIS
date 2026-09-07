"""
MT5 agent session management service -- TASK-301.

Tracks MT5 EA connection state, validates heartbeats, and enforces
the fail-closed rule: UNKNOWN or stale agents do not permit new entries.

Authority model:
  PostgreSQL: authoritative last_known_status + last_seen_at
  Redis: optional fast-path cache (non-authoritative)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import select

from backend.core.logging import get_logger
from backend.db.models.account import TradingAccount
from backend.db.models.mt5_agent import MT5Agent
from backend.services.audit import AuditEventType, Severity, record_audit_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("services.mt5_session")

HEARTBEAT_INTERVAL_MS: int = 5_000
MISSED_HEARTBEAT_THRESHOLD: int = 3
AGENT_TIMEOUT_SECONDS: int = (HEARTBEAT_INTERVAL_MS * MISSED_HEARTBEAT_THRESHOLD) // 1000

AgentStatus = Literal["UNKNOWN", "CONNECTED", "DISCONNECTED", "ERROR"]


async def process_agent_heartbeat(
    db: AsyncSession,
    agent_id: str,
    account_id: str,
    ea_version: str | None = None,
    mt5_version: str | None = None,
    terminal_connected: bool = True,
) -> MT5Agent | None:
    """Process a heartbeat from an MT5 EA and update agent state in PostgreSQL."""
    try:
        agent_uuid = uuid.UUID(agent_id)
        account_uuid = uuid.UUID(account_id)
    except ValueError:
        logger.warning(
            "mt5_session.heartbeat.invalid_uuid",
            agent_id=agent_id,
            account_id=account_id,
        )
        return None

    result = await db.execute(
        select(MT5Agent)
        .join(TradingAccount, MT5Agent.account_id == TradingAccount.id)
        .where(
            MT5Agent.id == agent_uuid,
            MT5Agent.account_id == account_uuid,
        )
    )
    agent: MT5Agent | None = result.scalar_one_or_none()

    if agent is None:
        logger.warning(
            "mt5_session.heartbeat.agent_not_found",
            agent_id=agent_id,
            account_id=account_id,
        )
        return None

    now_utc = datetime.now(UTC)
    previous_status = agent.last_known_status
    new_status: AgentStatus = "CONNECTED" if terminal_connected else "DISCONNECTED"

    agent.last_seen_at = now_utc
    agent.last_known_status = new_status
    if ea_version is not None:
        agent.ea_version = ea_version
    if mt5_version is not None:
        agent.mt5_version = mt5_version

    if previous_status != new_status:
        await record_audit_event(
            db,
            event_type=(
                AuditEventType.MT5_AGENT_CONNECTED
                if new_status == "CONNECTED"
                else AuditEventType.MT5_AGENT_DISCONNECTED
            ),
            account_id=agent.account_id,
            mt5_agent_id=agent.id,
            payload={
                "previous_status": previous_status,
                "new_status": new_status,
                "ea_version": ea_version,
                "mt5_version": mt5_version,
            },
        )

    logger.info(
        "mt5_session.heartbeat.processed",
        agent_id=agent_id,
        account_id=account_id,
        status=new_status,
    )
    return agent


async def mark_agent_offline(
    db: AsyncSession,
    agent_id: str,
    reason: str = "HEARTBEAT_TIMEOUT",
) -> None:
    """Mark an agent as DISCONNECTED due to missed heartbeats."""
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError:
        return

    result = await db.execute(select(MT5Agent).where(MT5Agent.id == agent_uuid))
    agent: MT5Agent | None = result.scalar_one_or_none()

    if agent is None or agent.last_known_status == "DISCONNECTED":
        return

    agent.last_known_status = "DISCONNECTED"
    await record_audit_event(
        db,
        event_type=AuditEventType.MT5_AGENT_DISCONNECTED,
        account_id=agent.account_id,
        mt5_agent_id=agent.id,
        severity=Severity.WARNING,
        payload={"reason": reason, "previous_status": "CONNECTED"},
    )
    logger.warning("mt5_session.agent_marked_offline", agent_id=agent_id, reason=reason)


async def get_agent_connection_state(
    db: AsyncSession,
    account_id: str,
) -> dict[str, object]:
    """Return PostgreSQL-authoritative connection state for the MT5 agent bound to account."""
    try:
        account_uuid = uuid.UUID(account_id)
    except ValueError:
        return {"status": "INVALID_ACCOUNT_ID", "connected": False}

    result = await db.execute(
        select(MT5Agent)
        .where(MT5Agent.account_id == account_uuid)
        .order_by(MT5Agent.created_at.desc())
        .limit(1)
    )
    agent: MT5Agent | None = result.scalar_one_or_none()

    if agent is None:
        return {"status": "NO_AGENT_REGISTERED", "connected": False}

    now_utc = datetime.now(UTC)
    if agent.last_seen_at is not None:
        stale_threshold = now_utc - timedelta(seconds=AGENT_TIMEOUT_SECONDS)
        is_stale = agent.last_seen_at < stale_threshold
    else:
        is_stale = True

    effective_status = agent.last_known_status
    if is_stale and effective_status == "CONNECTED":
        effective_status = "STALE"

    return {
        "agent_id": str(agent.id),
        "status": effective_status,
        "connected": effective_status == "CONNECTED",
        "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
        "ea_version": agent.ea_version,
        "mt5_version": agent.mt5_version,
    }


class MT5SessionService:
    """In-memory agent session tracking and watchdog service."""

    def __init__(self, heartbeat_timeout_seconds: int = AGENT_TIMEOUT_SECONDS) -> None:
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._agents: dict[str, dict[str, Any]] = {}

    def record_heartbeat(
        self,
        agent_id: str,
        account_id: str,
        status: str = "CONNECTED",
        account_number: str | None = None,
        ea_version: str | None = None,
    ) -> bool:
        self._agents[agent_id] = {
            "agent_id": agent_id,
            "account_id": account_id,
            "status": status,
            "account_number": account_number,
            "ea_version": ea_version,
            "last_seen_at": datetime.now(UTC),
        }
        return True

    def is_connected(self, agent_id: str) -> bool:
        rec = self._agents.get(agent_id)
        if not rec or rec.get("status") != "CONNECTED":
            return False
        last_seen = rec.get("last_seen_at")
        if not isinstance(last_seen, datetime):
            return False
        elapsed = (datetime.now(UTC) - last_seen).total_seconds()
        return bool(elapsed <= self.heartbeat_timeout_seconds)

