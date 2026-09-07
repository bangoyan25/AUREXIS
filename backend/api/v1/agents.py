"""
MT5 Agent management endpoints.

GET  /api/v1/agents                  — list agents for user's accounts
GET  /api/v1/agents/{agent_id}       — get single agent

Heartbeat endpoint is reserved for Phase 3 (TASK-301).
No live MT5 connection in this phase.
Redis is NOT the source of truth — PostgreSQL last_known_status is used.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.deps import get_current_user
from backend.core.logging import get_logger
from backend.db.models.account import TradingAccount
from backend.db.models.mt5_agent import MT5Agent
from backend.db.session import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["agents"])
logger = get_logger("api.agents")


class AgentResponse(BaseModel):
    id: str
    account_id: str
    label: str
    last_known_status: str
    last_seen_at: datetime | None
    mt5_version: str | None
    ea_version: str | None
    notes: str | None
    created_at: datetime


def _to_response(agent: MT5Agent) -> AgentResponse:
    return AgentResponse(
        id=str(agent.id),
        account_id=str(agent.account_id),
        label=agent.label,
        last_known_status=agent.last_known_status,
        last_seen_at=agent.last_seen_at,
        mt5_version=agent.mt5_version,
        ea_version=agent.ea_version,
        notes=agent.notes,
        created_at=agent.created_at,
    )


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[AgentResponse]:
    # Only return agents for accounts owned by this user
    accounts = await db.execute(
        select(TradingAccount.id).where(TradingAccount.user_id == uuid.UUID(user_id))
    )
    account_ids = [row[0] for row in accounts.all()]
    if not account_ids:
        return []
    result = await db.execute(
        select(MT5Agent)
        .where(MT5Agent.account_id.in_(account_ids))
        .order_by(MT5Agent.created_at)
    )
    return [_to_response(a) for a in result.scalars().all()]


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    result = await db.execute(
        select(MT5Agent)
        .join(TradingAccount, MT5Agent.account_id == TradingAccount.id)
        .where(
            MT5Agent.id == uuid.UUID(agent_id),
            TradingAccount.user_id == uuid.UUID(user_id),
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
    return _to_response(agent)
