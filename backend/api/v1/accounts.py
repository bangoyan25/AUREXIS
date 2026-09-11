"""
Account management REST endpoints.

GET    /api/v1/accounts          — list user's trading accounts
POST   /api/v1/accounts          — create a trading account
GET    /api/v1/accounts/{id}     — get single account
PATCH  /api/v1/accounts/{id}     — update account metadata
DELETE /api/v1/accounts/{id}     — deactivate account

Authorization: user can only access their own accounts.
Cent normalization: backend-side only (Decimal).
IDR conversion: NOT_CONFIGURED until FX provider defined.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.api.deps import get_current_user
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.models.account import TradingAccount
from backend.db.models.mt5_agent import MT5Agent
from backend.db.session import get_db
from backend.services import agent_commands as cmd_svc
from backend.services.audit import AuditEventType, record_audit_event
from backend.services.broker_adapter import (
    UnsupportedBrokerError,
    get_supported_brokers,
    normalize_broker_name,
)
from backend.services.license import check_user_can_create_account
from backend.ws.agent_manager import agent_manager
from backend.ws.agent_protocol import CommandMessage, CommandPayload

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["accounts"])
logger = get_logger("api.accounts")


class AccountResponse(BaseModel):
    id: str
    label: str
    broker: str
    mt5_account_number: str
    mt5_server: str | None
    broker_currency: str
    is_cent_account: bool
    cent_normalization_factor: str
    is_active: bool
    trading_enabled: bool
    idr_conversion: str
    created_at: datetime
    updated_at: datetime


class CreateAccountRequest(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    broker: str = Field(min_length=1, max_length=100)
    mt5_account_number: str = Field(min_length=1, max_length=50)
    mt5_server: str | None = Field(default=None, max_length=200)
    broker_currency: str = Field(default="USD", max_length=20)
    is_cent_account: bool = False
    cent_normalization_factor: str = "1.0"


class PatchAccountRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    mt5_server: str | None = None
    broker_currency: str | None = None
    mt5_account_number: str | None = None
    is_active: bool | None = None
    trading_enabled: bool | None = None


def _to_response(acct: TradingAccount) -> AccountResponse:
    return AccountResponse(
        id=str(acct.id),
        label=acct.label,
        broker=acct.broker,
        mt5_account_number=acct.mt5_account_number,
        mt5_server=acct.mt5_server,
        broker_currency=acct.broker_currency,
        is_cent_account=acct.is_cent_account,
        cent_normalization_factor=str(acct.cent_normalization_factor),
        is_active=acct.is_active,
        trading_enabled=acct.trading_enabled,
        idr_conversion="NOT_CONFIGURED" if not settings.FX_RATE_PROVIDER else "UNAVAILABLE",
        created_at=acct.created_at,
        updated_at=acct.updated_at,
    )


async def _owned(account_id: str, user_id: str, db: AsyncSession) -> TradingAccount:
    result = await db.execute(
        select(TradingAccount).where(
            TradingAccount.id == uuid.UUID(account_id),
            TradingAccount.user_id == uuid.UUID(user_id),
        )
    )
    acct = result.scalar_one_or_none()
    if acct is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
    return acct


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[AccountResponse]:
    result = await db.execute(
        select(TradingAccount)
        .where(TradingAccount.user_id == uuid.UUID(user_id))
        .order_by(TradingAccount.created_at)
    )
    return [_to_response(a) for a in result.scalars().all()]


@router.get("/accounts/brokers")
async def list_supported_brokers() -> list[dict[str, object]]:
    return get_supported_brokers()


@router.post("/accounts", response_model=AccountResponse, status_code=201)
async def create_account(
    body: CreateAccountRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    can_create, limit_err = await check_user_can_create_account(db, uuid.UUID(user_id))
    if not can_create:
        raise HTTPException(
            status_code=403,
            detail={"code": "LICENSE_ACCOUNT_LIMIT_REACHED", "message": limit_err or "Account limit reached"},
        )

    try:
        norm_broker = normalize_broker_name(body.broker)
    except UnsupportedBrokerError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNSUPPORTED_BROKER", "message": str(exc)},
        ) from exc

    try:
        factor = Decimal(body.cent_normalization_factor)
        if factor <= 0:
            raise ValueError
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_FACTOR", "message": "cent_normalization_factor must be a positive decimal"},
        ) from exc

    acct = TradingAccount(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        label=body.label,
        broker=norm_broker,
        mt5_account_number=body.mt5_account_number,
        mt5_server=body.mt5_server,
        broker_currency=body.broker_currency,
        is_cent_account=body.is_cent_account,
        cent_normalization_factor=factor,
        is_active=True,
        trading_enabled=False,
    )
    db.add(acct)
    await record_audit_event(
        db, AuditEventType.ACCOUNT_CREATED,
        user_id=uuid.UUID(user_id), account_id=acct.id,
        payload={"label": acct.label, "broker": acct.broker},
    )
    await db.flush()
    logger.info("accounts.created", account_id=str(acct.id))
    return _to_response(acct)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    return _to_response(await _owned(account_id, user_id, db))


@router.patch("/accounts/{account_id}", response_model=AccountResponse)
async def patch_account(
    account_id: str,
    body: PatchAccountRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    acct = await _owned(account_id, user_id, db)
    changed: dict[str, object] = {}
    if body.label is not None:
        acct.label = body.label
        changed["label"] = body.label
    if body.mt5_server is not None:
        acct.mt5_server = body.mt5_server
        changed["mt5_server"] = body.mt5_server
    if body.broker_currency is not None:
        acct.broker_currency = body.broker_currency
        changed["broker_currency"] = body.broker_currency
    if body.mt5_account_number is not None:
        acct.mt5_account_number = body.mt5_account_number
        changed["mt5_account_number"] = body.mt5_account_number
    if body.is_active is not None:
        acct.is_active = body.is_active
        changed["is_active"] = body.is_active
    if body.trading_enabled is not None:
        acct.trading_enabled = body.trading_enabled
        changed["trading_enabled"] = body.trading_enabled
    if changed:
        await record_audit_event(
            db, AuditEventType.ACCOUNT_UPDATED,
            user_id=uuid.UUID(user_id), account_id=acct.id, payload=changed,
        )
    return _to_response(acct)


@router.post("/accounts/{account_id}/verify-agent")
async def verify_agent(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Verify whether the MT5 Agent is connected and matches this account's credentials.
    """
    acct = await _owned(account_id, user_id, db)

    # 1. Check if an MT5Agent is registered for this account
    agent_res = await db.execute(select(MT5Agent).where(MT5Agent.account_id == acct.id))
    agent = agent_res.scalar_one_or_none()
    if agent is None:
        return {
            "verified": False,
            "status": "NO_AGENT",
            "message": "Belum ada MT5 Agent terdaftar untuk akun ini. Buat agent di menu Agents terlebih dahulu.",
        }

    agent_id_str = str(agent.id)
    if not agent_manager.is_connected(agent_id_str):
        return {
            "verified": False,
            "status": "AGENT_OFFLINE",
            "agent_id": agent_id_str,
            "agent_label": agent.label,
            "message": f"MT5 Agent '{agent.label}' offline. Pastikan EA AurexisAgent aktif di terminal MT5.",
        }

    # 2. Agent is connected over WebSocket. Send GET_STATUS command
    try:
        cmd = await cmd_svc.create_command(
            db=db,
            agent_id=agent.id,
            command_type="GET_STATUS",
            user_id=acct.user_id,
            account_id=acct.id,
        )
        await db.commit()

        # Send command directly to agent websocket
        delivered = await agent_manager.send_json(
            agent_id_str,
            CommandMessage(
                command=CommandPayload(
                    id=str(cmd.id),
                    command_type="GET_STATUS",
                    payload={},
                )
            ).model_dump(),
        )

        if delivered:
            await cmd_svc.mark_command_sent(db, agent.id, cmd.id)
            await db.commit()

        # Poll for command completion (up to 3 seconds)
        for _ in range(30):
            await asyncio.sleep(0.1)
            await db.refresh(cmd)
            if cmd.status in ("COMPLETED", "FAILED"):
                break

        if cmd.status == "COMPLETED" and cmd.result_json:
            res_data = json.loads(cmd.result_json)
            terminal_login = str(int(res_data.get("login", 0)))
            terminal_server = str(res_data.get("server", ""))
            terminal_currency = str(res_data.get("currency", ""))
            trade_allowed = bool(res_data.get("trade_allowed", 0))
            is_demo = bool(res_data.get("is_demo", False))

            is_match = terminal_login == str(acct.mt5_account_number)
            if is_match:
                if terminal_server and acct.mt5_server != terminal_server:
                    acct.mt5_server = terminal_server
                if terminal_currency and acct.broker_currency != terminal_currency:
                    acct.broker_currency = terminal_currency
                await db.commit()

                return {
                    "verified": True,
                    "status": "VERIFIED",
                    "agent_id": agent_id_str,
                    "agent_label": agent.label,
                    "terminal_login": terminal_login,
                    "terminal_server": terminal_server,
                    "terminal_currency": terminal_currency,
                    "trade_allowed": trade_allowed,
                    "is_demo": is_demo,
                    "message": f"Akun {terminal_login} terverifikasi aktif di terminal MT5 ({terminal_server})!",
                }
            else:
                return {
                    "verified": False,
                    "status": "ACCOUNT_MISMATCH",
                    "agent_id": agent_id_str,
                    "agent_label": agent.label,
                    "terminal_login": terminal_login,
                    "expected_login": acct.mt5_account_number,
                    "terminal_server": terminal_server,
                    "message": f"Akun di MT5 ({terminal_login}) tidak cocok dengan settingan akun ({acct.mt5_account_number}).",
                }

    except Exception as exc:
        logger.warning("verify_agent.query_error", error=str(exc))

    return {
        "verified": True,
        "status": "CONNECTED",
        "agent_id": agent_id_str,
        "agent_label": agent.label,
        "message": "MT5 Agent terhubung aktif ke backend AUREXIS.",
    }


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> None:
    acct = await _owned(account_id, user_id, db)
    if acct.trading_enabled:
        raise HTTPException(
            status_code=409,
            detail={"code": "TRADING_ENABLED", "message": "Disable trading before deleting"},
        )
    acct.is_active = False
    await record_audit_event(
        db, AuditEventType.ACCOUNT_DELETED,
        user_id=uuid.UUID(user_id), account_id=acct.id,
        payload={"label": acct.label},
    )
    logger.info("accounts.deactivated", account_id=account_id)

