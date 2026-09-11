"""
Strategy Engine API Endpoints — Phase 4B.

Provides authenticated, tenant-isolated controls for the AUREXIS Strategy Engine.

Endpoints (all under /api/v1):
- GET  /accounts/{account_id}/strategy              -> read engine state + last signal info
- POST /accounts/{account_id}/strategy/enable       -> enable strategy (dry_run=True by default)
- POST /accounts/{account_id}/strategy/disable      -> disable strategy
- POST /accounts/{account_id}/strategy/evaluate     -> run one evaluation cycle manually
- GET  /accounts/{account_id}/strategy/signals/latest -> latest CandidateSignal for account
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user
from backend.db.models.account import TradingAccount
from backend.db.models.risk import RiskConfiguration
from backend.db.models.signal import CandidateSignal as DbCandidateSignal
from backend.db.session import get_db
from backend.services import market_data_service, strategy_service

router = APIRouter(tags=["strategy-engine"])


async def _verify_account_ownership(
    db: AsyncSession,
    account_id_str: str,
    user_id_str: str,
) -> TradingAccount:
    """Validate UUID format and ensure account belongs to authenticated user."""
    try:
        account_uuid = uuid.UUID(account_id_str)
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        ) from None

    stmt = select(TradingAccount).where(
        TradingAccount.id == account_uuid,
        TradingAccount.user_id == user_uuid,
    )
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )
    return account


class StrategyStateResponse(BaseModel):
    account_id: str
    enabled: bool
    dry_run: bool
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    last_signal_direction: str | None = None
    last_signal_at: str | None = None
    last_signal_candle_ts: str | None = None
    last_signal_reason: str | None = None
    last_risk_decision: str | None = None
    last_risk_reason_code: str | None = None
    last_execution_status: str | None = None
    bars_count: int = 0
    warmup_status: str = "BARS_WARMING_UP"


class CandidateSignalResponse(BaseModel):
    id: str
    symbol: str
    direction: str
    strategy_id: str
    strategy_version: str
    setup_type: str | None = None
    confidence_score: str | None = None
    entry_reference: str | None = None
    suggested_stop_loss: str | None = None
    suggested_take_profit: str | None = None
    spread_at_signal: str | None = None
    news_state_at_signal: str | None = None
    status: str
    generated_at: str
    expires_at: str | None = None


class LatestSignalResponse(BaseModel):
    account_id: str
    signal: CandidateSignalResponse | None = None


class EnableStrategyRequest(BaseModel):
    dry_run: bool = Field(
        default=True,
        description="Dry-run mode: evaluate signals and risk but do NOT execute orders.",
    )


def _state_to_response(state: Any, bars_count: int = 0) -> StrategyStateResponse:
    warmup_status = "READY" if bars_count >= 50 else "BARS_WARMING_UP"
    return StrategyStateResponse(
        account_id=str(state.account_id),
        enabled=state.enabled,
        dry_run=state.dry_run,
        strategy_id=state.strategy_id,
        strategy_version=state.strategy_version,
        symbol=state.symbol,
        timeframe=state.timeframe,
        last_signal_direction=state.last_signal_direction,
        last_signal_at=state.last_signal_at.isoformat() if state.last_signal_at else None,
        last_signal_candle_ts=(
            state.last_signal_candle_ts.isoformat() if state.last_signal_candle_ts else None
        ),
        last_signal_reason=state.last_signal_reason,
        last_risk_decision=state.last_risk_decision,
        last_risk_reason_code=state.last_risk_reason_code,
        last_execution_status=state.last_execution_status,
        bars_count=bars_count,
        warmup_status=warmup_status,
    )


@router.get(
    "/accounts/{account_id}/strategy",
    response_model=StrategyStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get strategy engine state for an account",
)
async def get_strategy_state(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StrategyStateResponse:
    account = await _verify_account_ownership(db, account_id, user_id)
    state = await strategy_service.get_or_create_strategy_state(db, account.id)
    await db.commit()
    bars = await market_data_service.get_closed_bars(
        account.id, strategy_service.CANONICAL_SYMBOL, strategy_service.PRIMARY_TIMEFRAME
    )
    return _state_to_response(state, bars_count=len(bars))


@router.post(
    "/accounts/{account_id}/strategy/enable",
    response_model=StrategyStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Enable strategy engine for an account",
)
async def enable_strategy_endpoint(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: EnableStrategyRequest | None = None,
) -> StrategyStateResponse:
    """Enable the strategy engine. dry_run defaults to True — no broker orders without explicit opt-out."""
    account = await _verify_account_ownership(db, account_id, user_id)
    dry_run = body.dry_run if body is not None else True
    state = await strategy_service.enable_strategy(
        session=db,
        account_id=account.id,
        dry_run=dry_run,
    )
    await db.commit()
    bars = await market_data_service.get_closed_bars(
        account.id, strategy_service.CANONICAL_SYMBOL, strategy_service.PRIMARY_TIMEFRAME
    )
    return _state_to_response(state, bars_count=len(bars))


@router.post(
    "/accounts/{account_id}/strategy/disable",
    response_model=StrategyStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Disable strategy engine for an account",
)
async def disable_strategy_endpoint(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StrategyStateResponse:
    """Disable the strategy engine. No new positions will be opened after this."""
    account = await _verify_account_ownership(db, account_id, user_id)
    state = await strategy_service.disable_strategy(
        session=db,
        account_id=account.id,
    )
    await db.commit()
    bars = await market_data_service.get_closed_bars(
        account.id, strategy_service.CANONICAL_SYMBOL, strategy_service.PRIMARY_TIMEFRAME
    )
    return _state_to_response(state, bars_count=len(bars))


@router.post(
    "/accounts/{account_id}/strategy/evaluate",
    status_code=status.HTTP_200_OK,
    summary="Trigger one manual evaluation cycle",
)
async def evaluate_strategy_endpoint(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Run one evaluation cycle for the account's strategy engine."""
    account = await _verify_account_ownership(db, account_id, user_id)
    result = await strategy_service.evaluate_strategy_for_account(
        session=db,
        account_id=account.id,
    )
    await db.commit()
    return result


@router.get(
    "/accounts/{account_id}/strategy/signals/latest",
    response_model=LatestSignalResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest candidate signal for an account",
)
async def get_latest_signal(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LatestSignalResponse:
    """Return the most recent CandidateSignal for this account. Returns signal=null if none."""
    account = await _verify_account_ownership(db, account_id, user_id)
    stmt = (
        select(DbCandidateSignal)
        .where(DbCandidateSignal.account_id == account.id)
        .order_by(desc(DbCandidateSignal.generated_at))
        .limit(1)
    )
    res = await db.execute(stmt)
    sig = res.scalar_one_or_none()

    if sig is None:
        return LatestSignalResponse(account_id=str(account.id), signal=None)

    return LatestSignalResponse(
        account_id=str(account.id),
        signal=CandidateSignalResponse(
            id=str(sig.id),
            symbol=sig.symbol,
            direction=sig.direction,
            strategy_id=sig.strategy_id,
            strategy_version=sig.strategy_version,
            setup_type=sig.setup_type,
            confidence_score=str(sig.confidence_score) if sig.confidence_score is not None else None,
            entry_reference=str(sig.entry_reference) if sig.entry_reference is not None else None,
            suggested_stop_loss=(
                str(sig.suggested_stop_loss) if sig.suggested_stop_loss is not None else None
            ),
            suggested_take_profit=(
                str(sig.suggested_take_profit) if sig.suggested_take_profit is not None else None
            ),
            spread_at_signal=(
                str(sig.spread_at_signal) if sig.spread_at_signal is not None else None
            ),
            news_state_at_signal=sig.news_state_at_signal,
            status=sig.status,
            generated_at=sig.generated_at.isoformat(),
            expires_at=sig.expires_at.isoformat() if sig.expires_at is not None else None,
        ),
    )

class StrategyBarsResponse(BaseModel):
    account_id: str
    symbol: str
    timeframe: str
    count: int
    first_candle_ts: str | None = None
    last_candle_ts: str | None = None
    bars: list[dict[str, Any]]


@router.get(
    "/accounts/{account_id}/strategy/bars",
    response_model=StrategyBarsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get closed bars available to strategy engine for an account",
)
async def get_strategy_bars(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    timeframe: str = "M15",
) -> StrategyBarsResponse:
    account = await _verify_account_ownership(db, account_id, user_id)
    bars = await market_data_service.get_closed_bars(
        account.id, strategy_service.CANONICAL_SYMBOL, timeframe
    )
    first_ts = bars[0]["open_time"] if bars else None
    last_ts = bars[-1]["open_time"] if bars else None
    return StrategyBarsResponse(
        account_id=str(account.id),
        symbol=strategy_service.CANONICAL_SYMBOL,
        timeframe=timeframe,
        count=len(bars),
        first_candle_ts=first_ts,
        last_candle_ts=last_ts,
        bars=bars,
    )


class KillSwitchRequest(BaseModel):
    active: bool = Field(..., description="True to block all trading; False to resume")


class KillSwitchResponse(BaseModel):
    account_id: str
    kill_switch_active: bool
    status: str


@router.get(
    "/accounts/{account_id}/strategy/kill-switch",
    response_model=KillSwitchResponse,
    status_code=status.HTTP_200_OK,
    summary="Get kill switch status for account",
)
async def get_kill_switch(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KillSwitchResponse:
    account = await _verify_account_ownership(db, account_id, user_id)
    res = await db.execute(
        select(RiskConfiguration)
        .where(RiskConfiguration.account_id == account.id)
        .order_by(RiskConfiguration.version.desc())
        .limit(1)
    )
    risk_cfg = res.scalar_one_or_none()
    active = risk_cfg.kill_switch_active if risk_cfg else False
    return KillSwitchResponse(
        account_id=str(account.id),
        kill_switch_active=active,
        status="ACTIVE" if active else "DISARMED",
    )


@router.post(
    "/accounts/{account_id}/strategy/kill-switch",
    response_model=KillSwitchResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate or disarm account kill switch",
)
async def set_kill_switch(
    account_id: str,
    body: KillSwitchRequest,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KillSwitchResponse:
    """Activates or disarms the account kill switch.

    When active=True:
      - Sets kill_switch_active=True on RiskConfiguration.
      - Next RiskGate check will immediately BLOCK any execution.
      - Automatically disables the strategy engine for this account.
    """
    account = await _verify_account_ownership(db, account_id, user_id)

    res = await db.execute(
        select(RiskConfiguration)
        .where(RiskConfiguration.account_id == account.id)
        .order_by(RiskConfiguration.version.desc())
        .limit(1)
    )
    risk_cfg = res.scalar_one_or_none()

    if risk_cfg is None:
        import datetime
        risk_cfg = RiskConfiguration(
            account_id=account.id,
            version=1,
            effective_from=datetime.datetime.now(datetime.timezone.utc),
            kill_switch_active=body.active,
        )
        db.add(risk_cfg)
    else:
        risk_cfg.kill_switch_active = body.active

    # When engaging kill switch, also disable strategy engine
    if body.active:
        await strategy_service.disable_strategy(session=db, account_id=account.id)

    await db.commit()
    await db.refresh(risk_cfg)

    return KillSwitchResponse(
        account_id=str(account.id),
        kill_switch_active=risk_cfg.kill_switch_active,
        status="ACTIVE" if risk_cfg.kill_switch_active else "DISARMED",
    )

