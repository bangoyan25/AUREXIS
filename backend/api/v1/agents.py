"""
MT5 Agent management endpoints.

User-authenticated:
POST /api/v1/agents                  — register an agent for user's account
GET  /api/v1/agents                  — list agents for user's accounts
GET  /api/v1/agents/{agent_id}       — get single agent

Agent-authenticated (Bearer secret):
POST /api/v1/agents/{agent_id}/heartbeat — agent heartbeat and status report

The agent secret is returned only once during registration.
Only its bcrypt hash is persisted.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.api.deps import get_current_user
from backend.core.config import settings
from backend.db.models.account import TradingAccount
from backend.db.models.mt5_agent import MT5Agent
from backend.db.session import get_db
from backend.services.audit import AuditEventType, record_audit_event
from backend.services.auth import hash_password, verify_password

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["agents"])
_agent_bearer = HTTPBearer(auto_error=False)

ALLOWED_REPORTED_STATUSES = frozenset({"CONNECTED", "ERROR", "DISCONNECTED"})


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


class RegisterAgentRequest(BaseModel):
    account_id: str
    label: str = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)


class RegisterAgentResponse(AgentResponse):
    # Returned exactly once during registration.
    # Never persisted in plaintext and never included in normal GET responses.
    agent_secret: str


class AgentHeartbeatRequest(BaseModel):
    status: str | None = Field(
        default="CONNECTED",
        description="Reported status: CONNECTED | ERROR | DISCONNECTED",
    )
    mt5_version: str | None = Field(default=None, max_length=50)
    ea_version: str | None = Field(default=None, max_length=50)


class AgentHeartbeatResponse(BaseModel):
    status: str
    last_seen_at: datetime
    server_time: datetime


def _to_response(agent: MT5Agent) -> AgentResponse:
    from backend.ws.agent_manager import agent_manager
    is_conn = agent_manager.is_connected(str(agent.id))
    status_val = "CONNECTED" if is_conn else agent.last_known_status

    return AgentResponse(
        id=str(agent.id),
        account_id=str(agent.account_id),
        label=agent.label,
        last_known_status=status_val,
        last_seen_at=agent.last_seen_at,
        mt5_version=agent.mt5_version,
        ea_version=agent.ea_version,
        notes=agent.notes,
        created_at=agent.created_at,
    )


async def _get_agent_secret(
    credentials: HTTPAuthorizationCredentials | None = Depends(_agent_bearer),
) -> str:
    """Extract agent authentication bearer token."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Agent authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def _owned_account(
    account_id: str,
    user_id: str,
    db: AsyncSession,
) -> TradingAccount:
    try:
        account_uuid = uuid.UUID(account_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND"},
        ) from exc

    result = await db.execute(
        select(TradingAccount).where(
            TradingAccount.id == account_uuid,
            TradingAccount.user_id == user_uuid,
        )
    )
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND"},
        )

    return account


@router.post(
    "/agents",
    response_model=RegisterAgentResponse,
    status_code=201,
)
async def register_agent(
    body: RegisterAgentRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> RegisterAgentResponse:
    """
    Register a new MT5 EA agent for an account owned by the current user.

    The generated secret is returned once.
    Only the bcrypt hash is stored in PostgreSQL.
    """
    account = await _owned_account(body.account_id, user_id, db)

    agent_secret = secrets.token_urlsafe(48)

    agent = MT5Agent(
        id=uuid.uuid4(),
        account_id=account.id,
        label=body.label,
        hashed_secret=hash_password(agent_secret),
        last_known_status="UNKNOWN",
        last_seen_at=None,
        mt5_version=None,
        ea_version=None,
        notes=body.notes,
    )

    db.add(agent)
    await db.flush()


    await record_audit_event(
        db,
        AuditEventType.MT5_AGENT_REGISTERED,
        user_id=uuid.UUID(user_id),
        account_id=account.id,
        mt5_agent_id=agent.id,
        payload={
            "label": agent.label,
        },
    )

    await db.flush()

    response = _to_response(agent)

    return RegisterAgentResponse(
        **response.model_dump(),
        agent_secret=agent_secret,
    )


@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[AgentResponse]:
    """Return agents belonging to accounts owned by the current user."""
    accounts = await db.execute(
        select(TradingAccount.id).where(
            TradingAccount.user_id == uuid.UUID(user_id)
        )
    )
    account_ids = [row[0] for row in accounts.all()]

    if not account_ids:
        return []

    result = await db.execute(
        select(MT5Agent)
        .where(MT5Agent.account_id.in_(account_ids))
        .order_by(MT5Agent.created_at)
    )

    return [_to_response(agent) for agent in result.scalars().all()]


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    try:
        agent_uuid = uuid.UUID(agent_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND"},
        ) from exc

    result = await db.execute(
        select(MT5Agent)
        .join(TradingAccount, MT5Agent.account_id == TradingAccount.id)
        .where(
            MT5Agent.id == agent_uuid,
            TradingAccount.user_id == user_uuid,
        )
    )

    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND"},
        )

    return _to_response(agent)


@router.post(
    "/agents/{agent_id}/heartbeat",
    response_model=AgentHeartbeatResponse,
    status_code=200,
)
async def agent_heartbeat(
    agent_id: str,
    body: AgentHeartbeatRequest | None = None,
    secret: str = Depends(_get_agent_secret),
    db: AsyncSession = Depends(get_db),
) -> AgentHeartbeatResponse:
    """
    MT5 EA agent heartbeat endpoint.

    Authenticates the agent using its registered agent secret (Bearer auth).
    Updates last_seen_at, last_known_status, and optionally mt5_version / ea_version.
    Does NOT require a user JWT.
    """
    try:
        agent_uuid = uuid.UUID(agent_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND"},
        ) from exc

    result = await db.execute(
        select(MT5Agent).where(MT5Agent.id == agent_uuid)
    )
    agent = result.scalar_one_or_none()

    # Fail closed with 401 to avoid leaking agent existence
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid agent credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(secret, agent.hashed_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid agent credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    now = datetime.now(UTC)
    agent.last_seen_at = now

    req_status = (body.status if body and body.status else "CONNECTED").upper()
    if req_status not in ALLOWED_REPORTED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_STATUS", "message": f"Status must be one of: {sorted(ALLOWED_REPORTED_STATUSES)}"},
        )

    prev_status = agent.last_known_status
    agent.last_known_status = req_status

    if body:
        if body.mt5_version is not None:
            agent.mt5_version = body.mt5_version
        if body.ea_version is not None:
            agent.ea_version = body.ea_version

    # Audit status transition if transitioned to CONNECTED or DISCONNECTED
    if req_status == "CONNECTED" and prev_status != "CONNECTED":
        await record_audit_event(
            db,
            AuditEventType.MT5_AGENT_CONNECTED,
            account_id=agent.account_id,
            mt5_agent_id=agent.id,
            payload={
                "label": agent.label,
                "mt5_version": agent.mt5_version,
                "ea_version": agent.ea_version,
            },
        )
    elif req_status == "DISCONNECTED" and prev_status != "DISCONNECTED":
        await record_audit_event(
            db,
            AuditEventType.MT5_AGENT_DISCONNECTED,
            account_id=agent.account_id,
            mt5_agent_id=agent.id,
            payload={"label": agent.label},
        )

    await db.flush()

    return AgentHeartbeatResponse(
        status=agent.last_known_status,
        last_seen_at=agent.last_seen_at,
        server_time=now,
    )
