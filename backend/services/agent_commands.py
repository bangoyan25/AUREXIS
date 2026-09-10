"""
Agent Command Service.

Handles lifecycle of control-plane commands between AUREXIS and MT5 Agents.
Implements state machine:
  PENDING -> SENT -> ACKNOWLEDGED -> COMPLETED | FAILED
  PENDING / SENT -> EXPIRED

Enforces:
- Only supported command types (PING, GET_STATUS)
- Strict state transition rules
- Agent and account scoping
- Audit logging (no secrets in audit payloads)
- Atomic claim to avoid double execution
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.core.logging import get_logger
from backend.db.models.agent_command import MT5AgentCommand
from backend.services.audit import AuditEventType, record_audit_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("service.agent_commands")

SUPPORTED_COMMAND_TYPES = frozenset({"PING", "GET_STATUS"})

VALID_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"SENT", "FAILED", "EXPIRED"},
    "SENT": {"ACKNOWLEDGED", "COMPLETED", "FAILED", "EXPIRED"},
    "ACKNOWLEDGED": {"COMPLETED", "FAILED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "EXPIRED": set(),
}


class CommandError(Exception):
    """Base domain exception for command service."""


class InvalidCommandTypeError(CommandError):
    """Raised when an unsupported command type is requested."""


class InvalidStateTransitionError(CommandError):
    """Raised when a state transition violates the lifecycle state machine."""


class CommandNotFoundError(CommandError):
    """Raised when command does not exist or does not belong to specified agent."""


async def create_command(
    db: AsyncSession,
    agent_id: uuid.UUID,
    command_type: str,
    payload: dict[str, Any] | None = None,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> MT5AgentCommand:
    """
    Create a new control command queued for an MT5 EA.

    command_type must be in SUPPORTED_COMMAND_TYPES.
    Initial status is always PENDING.
    """
    upper_type = command_type.upper()
    if upper_type not in SUPPORTED_COMMAND_TYPES:
        raise InvalidCommandTypeError(
            f"Unsupported command_type '{command_type}'. Allowed: {sorted(SUPPORTED_COMMAND_TYPES)}"
        )

    payload_json: str | None = None
    if payload is not None:
        try:
            payload_json = json.dumps(payload, default=str)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"Payload cannot be serialized to JSON: {exc}") from exc

    command = MT5AgentCommand(
        id=uuid.uuid4(),
        agent_id=agent_id,
        command_type=upper_type,
        status="PENDING",
        payload_json=payload_json,
        result_json=None,
        error_message=None,
        sent_at=None,
        acknowledged_at=None,
        completed_at=None,
    )
    db.add(command)

    await record_audit_event(
        db,
        AuditEventType.MT5_AGENT_COMMAND_CREATED,
        user_id=user_id,
        account_id=account_id,
        mt5_agent_id=agent_id,
        payload={
            "command_id": str(command.id),
            "command_type": upper_type,
        },
    )

    await db.flush()
    return command


async def get_command(
    db: AsyncSession,
    agent_id: uuid.UUID,
    command_id: uuid.UUID,
) -> MT5AgentCommand | None:
    """Retrieve command by ID, ensuring it belongs to agent_id."""
    result = await db.execute(
        select(MT5AgentCommand).where(
            MT5AgentCommand.id == command_id,
            MT5AgentCommand.agent_id == agent_id,
        )
    )
    return result.scalar_one_or_none()


async def list_commands(
    db: AsyncSession,
    agent_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[MT5AgentCommand]:
    """List commands for an agent ordered latest first."""
    result = await db.execute(
        select(MT5AgentCommand)
        .where(MT5AgentCommand.agent_id == agent_id)
        .order_by(MT5AgentCommand.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def claim_pending_commands(
    db: AsyncSession,
    agent_id: uuid.UUID,
    limit: int = 10,
    account_user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> list[MT5AgentCommand]:
    """
    Atomically claim PENDING commands for the agent.

    Transitions PENDING -> SENT, sets sent_at = now(UTC).
    Subsequent calls will not return already claimed commands.
    """
    now = datetime.now(UTC)
    result = await db.execute(
        select(MT5AgentCommand)
        .where(
            MT5AgentCommand.agent_id == agent_id,
            MT5AgentCommand.status == "PENDING",
        )
        .order_by(MT5AgentCommand.created_at.asc())
        .limit(limit)
    )
    commands = list(result.scalars().all())

    for cmd in commands:
        cmd.status = "SENT"
        cmd.sent_at = now
        await record_audit_event(
            db,
            AuditEventType.MT5_AGENT_COMMAND_SENT,
            user_id=account_user_id,
            account_id=account_id,
            mt5_agent_id=agent_id,
            payload={
                "command_id": str(cmd.id),
                "command_type": cmd.command_type,
            },
        )

    if commands:
        await db.flush()

    return commands

async def has_in_flight_command(db: AsyncSession, agent_id: uuid.UUID) -> bool:
    """Return True if agent currently has an active command (SENT or ACKNOWLEDGED)."""
    result = await db.execute(
        select(MT5AgentCommand.id).where(
            MT5AgentCommand.agent_id == agent_id,
            MT5AgentCommand.status.in_(("SENT", "ACKNOWLEDGED")),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None




async def acknowledge_command(
    db: AsyncSession,
    agent_id: uuid.UUID,
    command_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> MT5AgentCommand:
    """Mark command ACKNOWLEDGED by the EA agent."""
    cmd = await get_command(db, agent_id, command_id)
    if cmd is None:
        raise CommandNotFoundError(f"Command {command_id} not found for agent {agent_id}")

    if "ACKNOWLEDGED" not in VALID_TRANSITIONS.get(cmd.status, set()):
        raise InvalidStateTransitionError(
            f"Cannot transition command from {cmd.status} to ACKNOWLEDGED"
        )

    now = datetime.now(UTC)
    cmd.status = "ACKNOWLEDGED"
    cmd.acknowledged_at = now

    await record_audit_event(
        db,
        AuditEventType.MT5_AGENT_COMMAND_ACKNOWLEDGED,
        user_id=user_id,
        account_id=account_id,
        mt5_agent_id=agent_id,
        payload={
            "command_id": str(cmd.id),
            "command_type": cmd.command_type,
        },
    )

    await db.flush()
    return cmd


async def complete_command(
    db: AsyncSession,
    agent_id: uuid.UUID,
    command_id: uuid.UUID,
    result: dict[str, Any] | None = None,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> MT5AgentCommand:
    """Mark command COMPLETED with optional result blob."""
    cmd = await get_command(db, agent_id, command_id)
    if cmd is None:
        raise CommandNotFoundError(f"Command {command_id} not found for agent {agent_id}")

    if "COMPLETED" not in VALID_TRANSITIONS.get(cmd.status, set()):
        raise InvalidStateTransitionError(
            f"Cannot transition command from {cmd.status} to COMPLETED"
        )

    now = datetime.now(UTC)
    cmd.status = "COMPLETED"
    cmd.completed_at = now
    if result is not None:
        try:
            cmd.result_json = json.dumps(result, default=str)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"Result cannot be serialized to JSON: {exc}") from exc

    await record_audit_event(
        db,
        AuditEventType.MT5_AGENT_COMMAND_COMPLETED,
        user_id=user_id,
        account_id=account_id,
        mt5_agent_id=agent_id,
        payload={
            "command_id": str(cmd.id),
            "command_type": cmd.command_type,
        },
    )

    await db.flush()
    return cmd


async def fail_command(
    db: AsyncSession,
    agent_id: uuid.UUID,
    command_id: uuid.UUID,
    error_message: str | None = None,
    user_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> MT5AgentCommand:
    """Mark command FAILED with reported error message."""
    cmd = await get_command(db, agent_id, command_id)
    if cmd is None:
        raise CommandNotFoundError(f"Command {command_id} not found for agent {agent_id}")

    if "FAILED" not in VALID_TRANSITIONS.get(cmd.status, set()):
        raise InvalidStateTransitionError(
            f"Cannot transition command from {cmd.status} to FAILED"
        )

    now = datetime.now(UTC)
    cmd.status = "FAILED"
    cmd.completed_at = now
    if error_message:
        cmd.error_message = error_message[:500]

    await record_audit_event(
        db,
        AuditEventType.MT5_AGENT_COMMAND_FAILED,
        user_id=user_id,
        account_id=account_id,
        mt5_agent_id=agent_id,
        payload={
            "command_id": str(cmd.id),
            "command_type": cmd.command_type,
            "error_message": cmd.error_message,
        },
    )

    await db.flush()
    return cmd
