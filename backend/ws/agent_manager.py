"""
Agent Connection Manager.

Tracks connected MT5 EA agents and manages bidirectional delivery queues.
Single connection per agent: reconnects disconnect the previous active connection
cleanly so that commands are delivered to the latest live connection only.
PostgreSQL remains the single source of truth for command states.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = get_logger("ws.agent_manager")


class AgentConnectionManager:
    """
    Manages active MT5 agent WebSocket connections in memory.
    Enforces one active connection per agent_id.
    """

    def __init__(self) -> None:
        # agent_id_str -> WebSocket
        self._active_connections: dict[str, WebSocket] = {}
        # agent_id_str -> lock for delivery operations
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, agent_id: str) -> asyncio.Lock:
        if agent_id not in self._locks:
            self._locks[agent_id] = asyncio.Lock()
        return self._locks[agent_id]

    async def connect(self, agent_id: str, websocket: WebSocket) -> None:
        """
        Accept connection and register as active agent.
        If an existing connection exists for this agent, gracefully close it
        to prevent split-brain delivery.
        """
        old_ws = self._active_connections.get(agent_id)
        if old_ws is not None and old_ws is not websocket:
            logger.info("agent_ws.replacing_connection", agent_id=agent_id)
            try:
                await old_ws.close(code=1000, reason="Replaced by new connection")
            except Exception:
                pass

        await websocket.accept()
        self._active_connections[agent_id] = websocket
        logger.info("agent_ws.connected", agent_id=agent_id)

    def disconnect(self, agent_id: str, websocket: WebSocket) -> None:
        """
        Remove websocket if it is the active one for this agent.
        """
        current_ws = self._active_connections.get(agent_id)
        if current_ws is websocket:
            self._active_connections.pop(agent_id, None)
            logger.info("agent_ws.disconnected", agent_id=agent_id)

    def is_connected(self, agent_id: str) -> bool:
        """Return True if agent has an active connection."""
        return agent_id in self._active_connections

    async def send_json(self, agent_id: str, data: dict[str, Any]) -> bool:
        """
        Deliver a JSON message to an agent.
        Returns True if delivered, False if agent is disconnected or delivery failed.
        """
        ws = self._active_connections.get(agent_id)
        if ws is None:
            return False

        async with self._get_lock(agent_id):
            try:
                await ws.send_json(data)
                return True
            except Exception as exc:
                logger.warning(
                    "agent_ws.send_failed",
                    agent_id=agent_id,
                    error=str(exc),
                )
                self.disconnect(agent_id, ws)
                return False

    @property
    def connection_count(self) -> int:
        return len(self._active_connections)


# Singleton manager
agent_manager = AgentConnectionManager()
