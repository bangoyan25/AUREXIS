"""
WebSocket connection manager for AUREXIS.

Manages active WebSocket connections.
Broadcasts server-controlled events to authenticated connected clients.
The frontend is a passive consumer — no trading decisions are made client-side.

Event routing:
- Broadcast to all: system-wide events (SYSTEM_ALERT, etc.)
- Account-scoped: events for a specific account (RISK_STATE_CHANGED, etc.)
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import WebSocket

    from backend.ws.events import WsEvent

logger = get_logger("ws.manager")


class ConnectionManager:
    """
    Thread-safe (single-process) WebSocket connection manager.

    For multi-process/multi-instance deployment, replace the in-memory
    connection store with Redis pub/sub subscriptions.
    """

    def __init__(self) -> None:
        # Map: account_id → set of active WebSocket connections
        self._account_connections: dict[str, set[WebSocket]] = defaultdict(set)
        # Connections not associated with a specific account (e.g., system health)
        self._global_connections: set[WebSocket] = set()

    async def connect(
        self,
        websocket: WebSocket,
        account_id: str | None = None,
    ) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if account_id:
            self._account_connections[account_id].add(websocket)
            logger.info(
                "ws.connected",
                account_id=account_id,
                total_for_account=len(self._account_connections[account_id]),
            )
        else:
            self._global_connections.add(websocket)
            logger.info("ws.connected_global", total_global=len(self._global_connections))

    def disconnect(
        self,
        websocket: WebSocket,
        account_id: str | None = None,
    ) -> None:
        """Remove a disconnected WebSocket from all connection sets."""
        if account_id:
            self._account_connections[account_id].discard(websocket)
        self._global_connections.discard(websocket)
        logger.info("ws.disconnected", account_id=account_id)

    async def broadcast_event(self, event: WsEvent) -> None:
        """
        Broadcast an event to relevant connected clients.

        Account-scoped events → only connections for that account.
        Non-scoped events → all global connections.
        System alerts → both account and global connections.
        """
        payload = event.model_dump_json()

        if event.account_id:
            await self._send_to_account(event.account_id, payload)

        # System alerts go to all global connections too
        if event.event == "SYSTEM_ALERT" or event.account_id is None:
            await self._send_to_all_global(payload)

    async def _send_to_account(self, account_id: str, payload: str) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._account_connections.get(account_id, set())):
            try:
                await ws.send_text(payload)
            except Exception as exc:
                logger.warning("ws.send_failed", account_id=account_id, error=str(exc))
                dead.add(ws)
        for ws in dead:
            self._account_connections[account_id].discard(ws)

    async def _send_to_all_global(self, payload: str) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._global_connections):
            try:
                await ws.send_text(payload)
            except Exception as exc:
                logger.warning("ws.global_send_failed", error=str(exc))
                dead.add(ws)
        for ws in dead:
            self._global_connections.discard(ws)

    @property
    def connection_count(self) -> int:
        """Total number of active connections across all accounts."""
        return len(self._global_connections) + sum(
            len(ws_set) for ws_set in self._account_connections.values()
        )


# Singleton connection manager — one per process
manager = ConnectionManager()
