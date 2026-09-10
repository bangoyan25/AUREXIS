"""
AUREXIS API v1 router.

Registers all v1 endpoint modules.
Each module handles its own sub-routing.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.v1 import (
    accounts,
    activity,
    agent_commands,
    agent_ws,
    agents,
    auth,
    health,
    market_data_routes,
    stubs,
    websocket,
)

router = APIRouter(prefix="/api/v1")

# Health (no auth required)
router.include_router(health.router)

# Realtime WebSocket
router.include_router(websocket.router)

# Authentication
router.include_router(auth.router, prefix="")

# Account management
router.include_router(accounts.router, prefix="")

# MT5 Agent management
router.include_router(agents.router, prefix="")

# MT5 Agent commands / control-plane
router.include_router(agent_commands.router, prefix="")

# Audit / Activity log
router.include_router(activity.router, prefix="")

# MT5 Agent WebSocket transport
router.include_router(agent_ws.router, prefix="")


# Market data & Risk gate observability
router.include_router(market_data_routes.router, prefix="")


# Domain stubs ? NOT_CONFIGURED/EMPTY boundaries for unimplemented domains
router.include_router(stubs.router, prefix="")
