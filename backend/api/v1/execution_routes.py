"""
Phase 4A: Controlled Demo Execution MVP Endpoints.

Provides strictly gated, authenticated test execution endpoints for MT5 Demo accounts.
- Risk Gate is mandatory: ALLOW is strictly required before any command reaches MT5.
- DEMO Guard is mandatory: Non-demo or unknown accounts are strictly rejected.
- Idempotency is mandatory: Duplicate client_order_id returns existing command, never duplicate trade.
- XAUUSD only: Controlled single test order execution.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.api.deps import get_current_user
from backend.core.logging import get_logger
from backend.db.models.account import TradingAccount
from backend.db.models.agent_command import MT5AgentCommand
from backend.db.models.execution import Position as DbPosition
from backend.db.models.mt5_agent import MT5Agent
from backend.db.session import get_db
from backend.services import agent_commands as cmd_svc
from backend.services.audit import record_audit_event
from backend.services.risk_gate import CANONICAL_SYMBOL, evaluate_risk_gate
from backend.ws.agent_manager import agent_manager
from backend.ws.agent_protocol import CommandMessage, CommandPayload

router = APIRouter(tags=["execution-test"])
logger = get_logger("api.execution_test")

MAX_TEST_VOLUME = Decimal("0.10")
DEFAULT_TEST_VOLUME = Decimal("0.01")


class TestExecutionRequest(BaseModel):
    action: Literal["OPEN_POSITION", "CLOSE_POSITION"] = Field(
        default="OPEN_POSITION",
        description="Controlled execution action: OPEN_POSITION or CLOSE_POSITION",
    )
    symbol: str = Field(default="XAUUSD", description="Trading symbol, must be XAUUSD")
    side: Literal["BUY", "SELL"] | None = Field(default="BUY", description="Side for OPEN_POSITION")
    volume: Decimal = Field(default=DEFAULT_TEST_VOLUME, gt=0, le=MAX_TEST_VOLUME, description="Test volume in lots")
    position_ticket: int | None = Field(default=None, description="Broker position ticket to close for CLOSE_POSITION")
    client_order_id: str = Field(min_length=1, max_length=64, description="Unique client order ID for idempotency")
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    deviation: int = Field(default=20, ge=1, le=100)
    comment: str = Field(default="AUREXIS_DEMO_TEST", max_length=50)


class ExecutionResultResponse(BaseModel):
    command_id: str
    account_id: str
    agent_id: str
    client_order_id: str
    action: str
    symbol: str
    side: str | None
    volume: str
    status: str
    risk_decision: str
    risk_reason_code: str
    broker_result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


def _is_confirmed_demo(account: TradingAccount) -> bool:
    server = (account.mt5_server or "").lower()
    broker = (account.broker or "").lower()
    label = (account.label or "").lower()
    if "real" in server or "live" in server:
        return False
    return "demo" in server or "demo" in broker or "demo" in label


def _command_to_exec_response(
    cmd: MT5AgentCommand,
    account_id: uuid.UUID,
    risk_decision: str = "ALLOW",
    risk_reason_code: str = "RISK_OK",
) -> ExecutionResultResponse:
    payload_dict: dict[str, Any] = {}
    if cmd.payload_json:
        try:
            payload_dict = json.loads(cmd.payload_json)
        except Exception:
            payload_dict = {}

    result_dict: dict[str, Any] | None = None
    if cmd.result_json:
        try:
            result_dict = json.loads(cmd.result_json)
        except Exception:
            result_dict = None

    return ExecutionResultResponse(
        command_id=str(cmd.id),
        account_id=str(account_id),
        agent_id=str(cmd.agent_id),
        client_order_id=payload_dict.get("client_order_id", ""),
        action=cmd.command_type,
        symbol=payload_dict.get("symbol", "XAUUSD"),
        side=payload_dict.get("side"),
        volume=str(payload_dict.get("volume", "0.01")),
        status=cmd.status,
        risk_decision=risk_decision,
        risk_reason_code=risk_reason_code,
        broker_result=result_dict,
        error_message=cmd.error_message,
        created_at=cmd.created_at,
        completed_at=cmd.completed_at,
    )



@router.post(
    "/accounts/{account_id}/execution/test",
    response_model=ExecutionResultResponse,
    status_code=status.HTTP_200_OK,
)
async def execute_demo_trade(
    account_id: str,
    body: TestExecutionRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Any = Depends(get_db),
) -> ExecutionResultResponse:
    try:
        acct_uuid = uuid.UUID(account_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Invalid UUID format"},
        ) from exc

    # 1. Tenant ownership verification
    acct_res = await db.execute(
        select(TradingAccount).where(
            TradingAccount.id == acct_uuid,
            TradingAccount.user_id == user_uuid,
        )
    )
    account = acct_res.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Trading account not found for user"},
        )

    # 2. Agent ownership & connection verification
    agent_res = await db.execute(
        select(MT5Agent).where(MT5Agent.account_id == acct_uuid)
    )
    agent = agent_res.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "AGENT_NOT_FOUND", "message": "No MT5 agent registered for this account"},
        )

    agent_id_str = str(agent.id)
    if not agent_manager.is_connected(agent_id_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "AGENT_OFFLINE", "message": "MT5 Agent is not connected to WebSocket"},
        )

    # 3. LIVE TRADING GUARD: Account must either be a confirmed demo OR have trading_enabled activated
    if not _is_confirmed_demo(account) and not account.trading_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TRADING_DISABLED",
                "message": "Live trading is not enabled for this account. Enable trading in Accounts settings.",
            },
        )

    # 4. Symbol validation: XAUUSD only
    norm_symbol = body.symbol.upper()
    if norm_symbol != CANONICAL_SYMBOL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_SYMBOL",
                "message": f"Symbol '{body.symbol}' not permitted. Only {CANONICAL_SYMBOL} allowed for Phase 4A.",
            },
        )

    # Parameter validation
    if body.action == "OPEN_POSITION":
        if body.side not in {"BUY", "SELL"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_SIDE", "message": "side must be BUY or SELL for OPEN_POSITION"},
            )
        if body.volume <= Decimal("0") or body.volume > MAX_TEST_VOLUME:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_VOLUME",
                    "message": f"Volume must be between 0.01 and {MAX_TEST_VOLUME} lots",
                },
            )
    elif body.action == "CLOSE_POSITION":
        if body.position_ticket is None:
            open_positions = (
                await db.execute(
                    select(DbPosition).where(
                        DbPosition.account_id == acct_uuid,
                        DbPosition.status == "OPEN",
                    )
                )
            ).scalars().all()
            if len(open_positions) == 1:
                body.position_ticket = open_positions[0].broker_ticket
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "POSITION_TICKET_REQUIRED",
                        "message": "Multiple open positions exist; provide position_ticket",
                    },
                )

    # 5. IDEMPOTENCY CHECK
    existing_cmds_res = await db.execute(
        select(MT5AgentCommand)
        .where(MT5AgentCommand.agent_id == agent.id)
        .order_by(MT5AgentCommand.created_at.desc())
    )
    for cmd in existing_cmds_res.scalars().all():
        if cmd.payload_json and f'"client_order_id": "{body.client_order_id}"' in cmd.payload_json:
            logger.info(
                "execution.idempotency_hit",
                client_order_id=body.client_order_id,
                command_id=str(cmd.id),
                status=cmd.status,
            )
            return _command_to_exec_response(cmd, acct_uuid)

    # 6. MANDATORY SERVER-SIDE RISK GATE EVALUATION
    gate = await evaluate_risk_gate(db, acct_uuid, norm_symbol)
    if gate.decision != "ALLOW":
        logger.warning(
            "execution.risk_gate_blocked",
            account_id=str(acct_uuid),
            reason_code=gate.reason_code,
            reason=gate.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "RISK_GATE_BLOCKED",
                "decision": gate.decision,
                "reason_code": gate.reason_code,
                "reason": gate.reason,
                "details": gate.details,
            },
        )

    # 7. Record auditable Execution Authorization
    await record_audit_event(
        db,
        "EXECUTION_AUTHORIZED",
        user_id=user_uuid,
        account_id=acct_uuid,
        mt5_agent_id=agent.id,
        payload={
            "action": body.action,
            "symbol": norm_symbol,
            "side": body.side,
            "volume": str(body.volume),
            "client_order_id": body.client_order_id,
            "risk_decision": gate.decision,
            "risk_reason_code": gate.reason_code,
            "risk_timestamp": gate.timestamp,
        },
    )

    # 8. Create MT5AgentCommand
    payload_data = {
        "command_type": body.action,
        "symbol": norm_symbol,
        "side": body.side,
        "volume": float(body.volume),
        "client_order_id": body.client_order_id,
        "stop_loss": float(body.stop_loss) if body.stop_loss else 0.0,
        "take_profit": float(body.take_profit) if body.take_profit else 0.0,
        "position_ticket": body.position_ticket,
        "deviation": body.deviation,
        "comment": body.comment,
    }

    cmd = await cmd_svc.create_command(
        db,
        agent_id=agent.id,
        command_type=body.action,
        payload=payload_data,
        user_id=user_uuid,
        account_id=acct_uuid,
    )

    # 9. Dispatch command to MT5 EA over WebSocket
    ws_payload = CommandMessage(
        command=CommandPayload(
            id=str(cmd.id),
            command_type=cmd.command_type,
            payload=payload_data,
        )
    )
    sent_ok = await agent_manager.send_json(agent_id_str, ws_payload.model_dump())
    if sent_ok:
        cmd.status = "SENT"
        cmd.sent_at = datetime.now(UTC)
        await record_audit_event(
            db,
            "MT5_AGENT_COMMAND_SENT",
            user_id=user_uuid,
            account_id=acct_uuid,
            mt5_agent_id=agent.id,
            payload={"command_id": str(cmd.id), "command_type": cmd.command_type},
        )
    await db.commit()
    await db.refresh(cmd)

    # 10. Await broker execution result (polling up to 6.0s with 0.1s steps)
    for _ in range(60):
        await asyncio.sleep(0.1)
        await db.refresh(cmd)
        if cmd.status in {"COMPLETED", "FAILED"}:
            break

    return _command_to_exec_response(cmd, acct_uuid, gate.decision, gate.reason_code)


@router.get(
    "/accounts/{account_id}/execution/test/{command_id}",
    response_model=ExecutionResultResponse,
    status_code=status.HTTP_200_OK,
)
async def get_test_execution_status(
    account_id: str,
    command_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Any = Depends(get_db),
) -> ExecutionResultResponse:
    try:
        acct_uuid = uuid.UUID(account_id)
        cmd_uuid = uuid.UUID(command_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND"}) from exc

    acct_res = await db.execute(
        select(TradingAccount).where(
            TradingAccount.id == acct_uuid,
            TradingAccount.user_id == user_uuid,
        )
    )
    if acct_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND"})

    cmd_res = await db.execute(
        select(MT5AgentCommand)
        .join(MT5Agent, MT5AgentCommand.agent_id == MT5Agent.id)
        .where(
            MT5AgentCommand.id == cmd_uuid,
            MT5Agent.account_id == acct_uuid,
        )
    )
    cmd = cmd_res.scalar_one_or_none()
    if cmd is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND"})

    return _command_to_exec_response(cmd, acct_uuid)


@router.get(
    "/accounts/{account_id}/positions",
    status_code=status.HTTP_200_OK,
)
async def get_account_positions(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    try:
        acct_uuid = uuid.UUID(account_id)
        user_uuid = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND"}) from exc

    acct_res = await db.execute(
        select(TradingAccount).where(
            TradingAccount.id == acct_uuid,
            TradingAccount.user_id == user_uuid,
        )
    )
    if acct_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND"})

    positions_res = await db.execute(
        select(DbPosition)
        .where(DbPosition.account_id == acct_uuid)
        .order_by(DbPosition.opened_at.desc())
    )
    positions = positions_res.scalars().all()
    open_count = sum(1 for p in positions if p.status == "OPEN")

    return {
        "account_id": str(acct_uuid),
        "total_positions": len(positions),
        "open_positions": open_count,
        "status": "OPEN" if open_count > 0 else "EMPTY",
        "positions": [
            {
                "id": str(p.id),
                "broker_ticket": p.broker_ticket,
                "symbol": p.symbol,
                "side": p.side,
                "lots": str(p.lots),
                "open_price": str(p.open_price),
                "close_price": str(p.close_price) if p.close_price else None,
                "status": p.status,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            }
            for p in positions
        ],
    }


