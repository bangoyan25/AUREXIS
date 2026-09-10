"""
MT5 Agent Command endpoints.

User-facing (JWT):
  POST /api/v1/agents/{agent_id}/commands
  GET  /api/v1/agents/{agent_id}/commands
  GET  /api/v1/agents/{agent_id}/commands/{command_id}

Agent-facing (Bearer agent_secret):
  GET  /api/v1/agents/{agent_id}/commands/pending
  POST /api/v1/agents/{agent_id}/commands/{command_id}/ack
  POST /api/v1/agents/{agent_id}/commands/{command_id}/result

Ownership:
- User endpoints verify the agent belongs to an account owned by the user.
- Agent endpoints authenticate via verify_password(secret, hashed_secret).
- Agent A cannot access Agent B commands.

No trading commands. Only: PING, GET_STATUS.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.api.deps import get_current_user
from backend.db.models.account import TradingAccount
from backend.db.models.agent_command import MT5AgentCommand
from backend.db.models.mt5_agent import MT5Agent
from backend.db.session import get_db
from backend.services import agent_commands as svc
from backend.services.auth import verify_password

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["agent-commands"])
_agent_bearer = HTTPBearer(auto_error=False)

ALLOWED_COMMAND_TYPES = frozenset({"PING", "GET_STATUS"})
MAX_PAYLOAD_SIZE = 4096  # bytes JSON-serialised


# -- Request / Response models --

class CreateCommandRequest(BaseModel):
    command_type: str = Field(description="PING or GET_STATUS")
    payload: dict[str, Any] | None = Field(default=None)


class CommandResponse(BaseModel):
    id: str
    agent_id: str
    command_type: str
    status: str
    payload: dict[str, Any] | None
    result: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None
    acknowledged_at: datetime | None
    completed_at: datetime | None


class AckRequest(BaseModel):
    status: str = Field(description="Must be ACKNOWLEDGED")


class ResultRequest(BaseModel):
    status: str = Field(description="COMPLETED or FAILED")
    result: dict[str, Any] | None = None
    error_message: str | None = Field(default=None, max_length=500)


# -- Helpers --

def _command_to_response(cmd: MT5AgentCommand) -> CommandResponse:
    payload_data: dict[str, Any] | None = None
    if cmd.payload_json:
        try:
            payload_data = json.loads(cmd.payload_json)
        except (json.JSONDecodeError, ValueError):
            payload_data = None

    result_data: dict[str, Any] | None = None
    if cmd.result_json:
        try:
            result_data = json.loads(cmd.result_json)
        except (json.JSONDecodeError, ValueError):
            result_data = None

    return CommandResponse(
        id=str(cmd.id),
        agent_id=str(cmd.agent_id),
        command_type=cmd.command_type,
        status=cmd.status,
        payload=payload_data,
        result=result_data,
        error_message=cmd.error_message,
        created_at=cmd.created_at,
        sent_at=cmd.sent_at,
        acknowledged_at=cmd.acknowledged_at,
        completed_at=cmd.completed_at,
    )


async def _get_agent_secret(
    credentials: HTTPAuthorizationCredentials | None = Depends(_agent_bearer),
) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Agent authentication required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def _verify_agent_auth(
    agent_id_str: str,
    secret: str,
    db: AsyncSession,
) -> tuple[MT5Agent, uuid.UUID | None]:
    """
    Authenticate agent by ID and plaintext secret. Fails closed with 401.
    Returns (agent, account_user_id) where account_user_id is from the account.
    """
    try:
        agent_uuid = uuid.UUID(agent_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND"},
        ) from exc

    result = await db.execute(
        select(MT5Agent, TradingAccount.user_id)
        .join(TradingAccount, MT5Agent.account_id == TradingAccount.id)
        .where(MT5Agent.id == agent_uuid)
    )
    row = result.first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid agent credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    agent, account_user_id = row

    if not verify_password(secret, agent.hashed_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid agent credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return agent, account_user_id


async def _assert_user_owns_agent(
    agent_id_str: str,
    user_id: str,
    db: AsyncSession,
) -> MT5Agent:
    """Verify user owns the account that the agent belongs to."""
    try:
        agent_uuid = uuid.UUID(agent_id_str)
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND"},
        )
    return agent


# -- User-facing endpoints --

@router.post(
    "/agents/{agent_id}/commands",
    response_model=CommandResponse,
    status_code=201,
)
async def create_command(
    agent_id: str,
    body: CreateCommandRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> CommandResponse:
    """
    Create a control-plane command for an MT5 EA agent.
    User must own the account that the agent belongs to.
    Only PING and GET_STATUS are supported at this phase.
    """
    agent = await _assert_user_owns_agent(agent_id, user_id, db)

    command_type_upper = body.command_type.upper() if body.command_type else ""
    if command_type_upper not in ALLOWED_COMMAND_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "UNSUPPORTED_COMMAND_TYPE",
                "message": f"command_type must be one of: {sorted(ALLOWED_COMMAND_TYPES)}",
            },
        )

    if body.payload is not None:
        payload_str = json.dumps(body.payload)
        if len(payload_str.encode()) > MAX_PAYLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "PAYLOAD_TOO_LARGE", "message": "Payload exceeds maximum size"},
            )

    try:
        cmd = await svc.create_command(
            db=db,
            agent_id=agent.id,
            command_type=command_type_upper,
            payload=body.payload,
            user_id=uuid.UUID(user_id),
            account_id=agent.account_id,
        )
    except svc.InvalidCommandTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "UNSUPPORTED_COMMAND_TYPE", "message": str(exc)},
        ) from exc
    except svc.CommandError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "COMMAND_ERROR", "message": str(exc)},
        ) from exc

    await db.commit()

    from backend.ws.agent_manager import agent_manager
    if agent_manager.is_connected(str(agent.id)):
        in_flight = await svc.has_in_flight_command(db, agent.id)
        if not in_flight:
            import asyncio
            from backend.api.v1.agent_ws import _deliver_pending_commands, _get_session_factory

            asyncio.create_task(
                _deliver_pending_commands(
                    agent.id, uuid.UUID(user_id), agent.account_id, _get_session_factory()
                )
            )

    return _command_to_response(cmd)


@router.get("/agents/{agent_id}/commands", response_model=list[CommandResponse])
async def list_commands(
    agent_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[CommandResponse]:
    """List commands for an agent. User must own the account."""
    agent = await _assert_user_owns_agent(agent_id, user_id, db)
    commands = await svc.list_commands(db, agent.id)
    return [_command_to_response(c) for c in commands]


# IMPORTANT: /pending MUST come before /{command_id} to avoid route ambiguity.
@router.get("/agents/{agent_id}/commands/pending", response_model=list[CommandResponse])
async def get_pending_commands(
    agent_id: str,
    secret: str = Depends(_get_agent_secret),
    db: AsyncSession = Depends(get_db),
) -> list[CommandResponse]:
    """
    Agent-authenticated endpoint: claim PENDING commands.

    Atomically transitions PENDING -> SENT for returned commands.
    Authenticated using Authorization: Bearer <agent_secret>.
    """
    agent, account_user_id = await _verify_agent_auth(agent_id, secret, db)
    commands = await svc.claim_pending_commands(db, agent.id, account_user_id=account_user_id, account_id=agent.account_id)
    return [_command_to_response(c) for c in commands]


@router.get("/agents/{agent_id}/commands/{command_id}", response_model=CommandResponse)
async def get_command(
    agent_id: str,
    command_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> CommandResponse:
    """Get a specific command. User must own the agent's account."""
    agent = await _assert_user_owns_agent(agent_id, user_id, db)

    try:
        command_uuid = uuid.UUID(command_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND"},
        ) from exc

    cmd = await svc.get_command(db, agent.id, command_uuid)
    if cmd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND"},
        )
    return _command_to_response(cmd)


# -- Agent-facing endpoints --

@router.post(
    "/agents/{agent_id}/commands/{command_id}/ack",
    response_model=CommandResponse,
    status_code=200,
)
async def ack_command(
    agent_id: str,
    command_id: str,
    body: AckRequest,
    secret: str = Depends(_get_agent_secret),
    db: AsyncSession = Depends(get_db),
) -> CommandResponse:
    """
    Agent acknowledges receipt of a command.
    body.status must be ACKNOWLEDGED.
    """
    if body.status.upper() != "ACKNOWLEDGED":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_STATUS", "message": "status must be ACKNOWLEDGED"},
        )

    agent, account_user_id = await _verify_agent_auth(agent_id, secret, db)

    try:
        command_uuid = uuid.UUID(command_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND"},
        ) from exc

    try:
        cmd = await svc.acknowledge_command(db, agent.id, command_uuid, user_id=account_user_id, account_id=agent.account_id)
    except svc.CommandNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND"},
        ) from exc
    except svc.InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_STATE_TRANSITION", "message": str(exc)},
        ) from exc

    return _command_to_response(cmd)


@router.post(
    "/agents/{agent_id}/commands/{command_id}/result",
    response_model=CommandResponse,
    status_code=200,
)
async def submit_result(
    agent_id: str,
    command_id: str,
    body: ResultRequest,
    secret: str = Depends(_get_agent_secret),
    db: AsyncSession = Depends(get_db),
) -> CommandResponse:
    """
    Agent submits final result or failure for a command.
    body.status must be COMPLETED or FAILED.
    """
    status_upper = body.status.upper() if body.status else ""
    if status_upper not in {"COMPLETED", "FAILED"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_STATUS", "message": "status must be COMPLETED or FAILED"},
        )

    agent, account_user_id = await _verify_agent_auth(agent_id, secret, db)

    try:
        command_uuid = uuid.UUID(command_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND"},
        ) from exc

    try:
        if status_upper == "COMPLETED":
            cmd = await svc.complete_command(
                db, agent.id, command_uuid,
                result=body.result,
                user_id=account_user_id,
                account_id=agent.account_id,
            )
        else:  # FAILED
            cmd = await svc.fail_command(
                db, agent.id, command_uuid,
                error_message=body.error_message,
                user_id=account_user_id,
                account_id=agent.account_id,
            )
    except svc.CommandNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND"},
        ) from exc
    except svc.InvalidStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_STATE_TRANSITION", "message": str(exc)},
        ) from exc

    return _command_to_response(cmd)
