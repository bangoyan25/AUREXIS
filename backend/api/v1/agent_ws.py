"""
Agent WebSocket Transport for MT5 EA.

Path: /api/v1/agents/{agent_id}/ws

Authentication:
- Authorization: Bearer <agent_secret> OR ?token=<agent_secret>
- Plaintext secret is NEVER logged.
- Verified against bcrypt hashed_secret in PostgreSQL.
- Fails closed with 4002 on any auth mismatch or nonexistent agent (no enumeration).

Protocol:
- Agent -> Server: hello | heartbeat | ack | result
- Server -> Agent: welcome | heartbeat_ack | command | error

PostgreSQL remains single source of truth for command states.
Commands are only marked SENT when handed to the active WebSocket connection.
If delivery fails, status is safely preserved as PENDING for retry or polling fallback.
"""

from __future__ import annotations

import json
import uuid
import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.core.logging import get_logger
from backend.db.models.account import TradingAccount
from backend.db.models.agent_command import MT5AgentCommand
from backend.db.models.mt5_agent import MT5Agent
from backend.db.session import AsyncSessionLocal
from backend.services import agent_commands as cmd_svc
from backend.services.audit import AuditEventType, record_audit_event
from backend.services.auth import verify_password
from backend.ws.agent_manager import agent_manager
from backend.ws.agent_protocol import (
    AckMessage,
    HeartbeatAckMessage,
    HeartbeatMessage,
    HelloMessage,
    ResultMessage,
    WelcomeMessage,
    parse_agent_message,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["agent-ws"])
logger = get_logger("ws.agent")

_session_factory = None


def _get_session_factory() -> Any:
    """Return active session factory (AsyncSessionLocal or test-injected)."""
    if _session_factory is not None:
        return _session_factory
    return AsyncSessionLocal


def _extract_agent_secret(websocket: WebSocket, query_token: str | None) -> str | None:
    """Extract secret from Authorization header or fallback query param. Never logs secret."""
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        secret = auth_header[7:].strip()
        if secret:
            return secret
    if query_token:
        return query_token.strip()
    return None


async def _authenticate_agent(
    agent_id_str: str,
    secret: str,
    db: AsyncSession,
) -> tuple[MT5Agent, uuid.UUID | None] | None:
    """Authenticate agent by UUID and bcrypt secret. Fails closed with None."""
    try:
        agent_uuid = uuid.UUID(agent_id_str)
    except ValueError:
        return None

    result = await db.execute(
        select(MT5Agent, TradingAccount.user_id)
        .join(TradingAccount, MT5Agent.account_id == TradingAccount.id)
        .where(MT5Agent.id == agent_uuid)
    )
    row = result.first()
    if row is None:
        return None

    agent, account_user_id = row
    if not verify_password(secret, agent.hashed_secret):
        return None

    return agent, account_user_id


async def _deliver_pending_commands(
    agent_id: uuid.UUID,
    account_user_id: uuid.UUID | None,
    account_id: uuid.UUID,
    session_factory: Any,
) -> int:
    """Claim in DB, commit, then deliver over WS without holding DB session."""
    async with session_factory() as db:
        claimed = await cmd_svc.claim_pending_commands(
            db, agent_id, account_user_id=account_user_id, account_id=account_id
        )
        await db.commit()

    if not claimed:
        return 0

    delivered_count = 0
    agent_id_str = str(agent_id)

    for cmd in claimed:
        payload_data: dict[str, Any] | None = None
        if cmd.payload_json:
            try:
                payload_data = json.loads(cmd.payload_json)
            except Exception:
                payload_data = None

        msg = {
            "type": "command",
            "command": {
                "id": str(cmd.id),
                "command_type": cmd.command_type,
                "payload": payload_data,
            },
        }

        sent = await agent_manager.send_json(agent_id_str, msg)
        if sent:
            delivered_count += 1
        else:
            try:
                async with session_factory() as db:
                    c_obj = await db.get(MT5AgentCommand, cmd.id)
                    if c_obj and c_obj.status == "SENT":
                        c_obj.status = "PENDING"
                        c_obj.sent_at = None
                        await db.commit()
            except Exception:
                pass
            logger.warning(
                "agent_ws.delivery_reverted",
                agent_id=agent_id_str,
                command_id=str(cmd.id),
            )
            break

    return delivered_count


@router.websocket("/agents/{agent_id}/ws")
async def agent_websocket_endpoint(
    websocket: WebSocket,
    agent_id: str,
    token: str | None = Query(default=None, description="Agent secret fallback"),
) -> None:
    """Bidirectional WebSocket transport for MT5 EA agents."""
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError:
        await websocket.close(code=4003, reason="Invalid agent_id")
        logger.warning("agent_ws.invalid_agent_id")
        return

    secret = _extract_agent_secret(websocket, token)
    if not secret:
        await websocket.close(code=4001, reason="Authentication required")
        logger.warning("agent_ws.no_secret", agent_id=agent_id)
        return

    session_factory = _get_session_factory()
    async with session_factory() as db:
        auth_res = await _authenticate_agent(agent_id, secret, db)
        if auth_res is None:
            await websocket.close(code=4002, reason="Authentication failed")
            logger.warning("agent_ws.auth_failed", agent_id=agent_id)
            return

        agent, account_user_id = auth_res
        now = datetime.now(UTC)
        agent.last_seen_at = now
        agent.last_known_status = "CONNECTED"

        await record_audit_event(
            db,
            AuditEventType.MT5_AGENT_CONNECTED,
            user_id=account_user_id,
            account_id=agent.account_id,
            mt5_agent_id=agent.id,
            payload={"label": agent.label, "transport": "websocket"},
        )
        await db.commit()

    agent_id_str = str(agent_uuid)
    await agent_manager.connect(agent_id_str, websocket)
    logger.info("agent_ws.established", agent_id=agent_id_str)

    await _deliver_pending_commands(agent_uuid, account_user_id, agent.account_id, session_factory)

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                if not isinstance(data, dict):
                    raise ValueError("Payload must be a JSON object")
                msg = parse_agent_message(data)
            except Exception as exc:
                await websocket.send_json(
                    {"type": "error", "code": "PROTOCOL_ERROR", "message": str(exc)}
                )
                continue

            if isinstance(msg, HelloMessage):
                async with session_factory() as db:
                    now = datetime.now(UTC)
                    res = await db.execute(select(MT5Agent).where(MT5Agent.id == agent_uuid))
                    curr = res.scalar_one_or_none()
                    if curr:
                        curr.last_seen_at = now
                        if msg.mt5_version:
                            curr.mt5_version = msg.mt5_version
                        if msg.ea_version:
                            curr.ea_version = msg.ea_version
                    await db.commit()
                await websocket.send_json(WelcomeMessage().model_dump())

            elif isinstance(msg, HeartbeatMessage):
                async with session_factory() as db:
                    now = datetime.now(UTC)
                    res = await db.execute(select(MT5Agent).where(MT5Agent.id == agent_uuid))
                    curr = res.scalar_one_or_none()
                    if curr:
                        curr.last_seen_at = now
                        if msg.mt5_version:
                            curr.mt5_version = msg.mt5_version
                        if msg.ea_version:
                            curr.ea_version = msg.ea_version
                    await db.commit()
                await websocket.send_json(HeartbeatAckMessage().model_dump())

            elif isinstance(msg, AckMessage):
                cmd_id = uuid.UUID(msg.command_id)
                err = None
                async with session_factory() as db:
                    try:
                        await cmd_svc.acknowledge_command(
                            db, agent_uuid, cmd_id,
                            user_id=account_user_id,
                            account_id=agent.account_id,
                        )
                        await db.commit()
                    except cmd_svc.CommandError as exc:
                        err = str(exc)
                if err:
                    await websocket.send_json({"type": "error", "code": "ACK_REJECTED", "message": err})

            elif isinstance(msg, ResultMessage):
                cmd_id = uuid.UUID(msg.command_id)
                err = None
                async with session_factory() as db:
                    try:
                        if msg.status == "COMPLETED":
                            await cmd_svc.complete_command(
                                db, agent_uuid, cmd_id,
                                result=msg.result,
                                user_id=account_user_id,
                                account_id=agent.account_id,
                            )
                        else:
                            await cmd_svc.fail_command(
                                db, agent_uuid, cmd_id,
                                error_message=msg.error_message,
                                user_id=account_user_id,
                                account_id=agent.account_id,
                            )
                        await db.commit()
                    except cmd_svc.CommandError as exc:
                        err = str(exc)
                if err:
                    await websocket.send_json({"type": "error", "code": "RESULT_REJECTED", "message": err})
                else:
                    await _deliver_pending_commands(
                        agent_uuid, account_user_id, agent.account_id, session_factory
                    )

    except (WebSocketDisconnect, asyncio.CancelledError):
        logger.info("agent_ws.client_disconnected", agent_id=agent_id_str)
    except Exception as exc:
        logger.warning("agent_ws.exception", agent_id=agent_id_str, error=str(exc))
    finally:
        agent_manager.disconnect(agent_id_str, websocket)
        logger.info("agent_ws.disconnected", agent_id=agent_id_str)
