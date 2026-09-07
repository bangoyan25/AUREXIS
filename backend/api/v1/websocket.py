"""
WebSocket endpoint for AUREXIS realtime events.

Authentication: REQUIRED. Token validated before connection accepted.
Authorization: DB-verified. Account ownership confirmed via PostgreSQL/SQLite.
Account A cannot subscribe to Account B's events.

Transport: token as query parameter (see adr/ADR-002-websocket-auth-transport.md).
Token is NEVER logged. Validation happens before accept().

Close codes:
- 4001: No token provided
- 4002: Invalid/expired token or authorization failed
- 4003: account_id not provided
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.core.logging import get_logger
from backend.db.models.account import TradingAccount
from backend.db.session import AsyncSessionLocal
from backend.services.auth import TokenError, decode_access_token
from backend.ws.manager import manager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["realtime"])
logger = get_logger("ws.endpoint")

# Module-level session factory — overridden in tests via monkeypatch.
# Production: AsyncSessionLocal (connects to PostgreSQL).
# Tests: injected SQLite session factory.
_session_factory = None


def _get_session_factory() -> Any:
    """Return the active session factory (production or test-injected)."""
    if _session_factory is not None:
        return _session_factory
    return AsyncSessionLocal


async def _resolve_and_authorize(
    token: str | None,
    account_id: str | None,
    db: AsyncSession | None = None,
) -> tuple[str, str] | None:
    """
    Validate JWT token and verify user owns the requested account.

    Returns (user_id, verified_account_id) on success, None on failure.

    db=None: JWT-only check (used in unit tests without a DB).
    db=AsyncSession: full DB ownership check (production path).

    A non-owned or nonexistent account yields the same None as a bad token —
    no information about other users' accounts is leaked.
    """
    if not token or not account_id:
        return None

    try:
        payload = decode_access_token(token)
    except TokenError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    if db is not None:
        try:
            account_uuid = uuid.UUID(account_id)
            user_uuid = uuid.UUID(str(user_id))
        except ValueError:
            return None

        result = await db.execute(
            select(TradingAccount.id).where(
                TradingAccount.id == account_uuid,
                TradingAccount.user_id == user_uuid,
            )
        )
        if result.scalar_one_or_none() is None:
            return None

    return str(user_id), account_id


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None, description="JWT access token (required)"),
    account_id: str | None = Query(default=None, description="Account ID to subscribe to"),
) -> None:
    """WebSocket endpoint for realtime event streaming."""
    # Stage 1: token present
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        logger.warning("ws.rejected_no_token")
        return

    # Stage 2: account_id present
    if not account_id:
        await websocket.close(code=4003, reason="account_id required")
        logger.warning("ws.rejected_no_account_id")
        return

    # Stage 3: validate token + DB ownership
    async with _get_session_factory()() as db:
        result = await _resolve_and_authorize(token, account_id, db=db)

    if result is None:
        await websocket.close(code=4002, reason="Authentication failed")
        logger.warning("ws.rejected_auth_failed", account_id=account_id)
        return

    user_id, verified_account_id = result

    await manager.connect(websocket, account_id=verified_account_id)
    logger.info("ws.connected", user_id=user_id, account_id=verified_account_id)

    try:
        while True:
            data = await websocket.receive_text()
            # Frontend is read-only — discard client messages
            logger.debug("ws.client_message_discarded", data_len=len(data))
    except WebSocketDisconnect:
        manager.disconnect(websocket, account_id=verified_account_id)
        logger.info("ws.disconnected_cleanly", account_id=verified_account_id)
    except Exception as exc:
        manager.disconnect(websocket, account_id=verified_account_id)
        logger.warning("ws.error", error=str(exc), account_id=verified_account_id)
