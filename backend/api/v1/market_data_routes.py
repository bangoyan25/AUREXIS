"""
Market Data & Risk Observability Endpoints.

Provides tenant-isolated read APIs for:
- Latest XAUUSD market tick & freshness
- Authoritative server-side Risk Gate decision & reason code
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user
from backend.db.models.account import TradingAccount
from backend.db.session import get_db
from backend.services import market_data_service
from backend.services.risk_gate import CANONICAL_SYMBOL, evaluate_risk_gate

router = APIRouter(tags=["market-data", "risk-gate"])


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


@router.get("/market/{account_id}/state")
async def get_account_market_state(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get latest market tick state and freshness for an account's trading stream.
    Strict tenant isolation: 404 if account does not belong to user.
    """
    account = await _verify_account_ownership(db, account_id, user_id)
    tick = await market_data_service.get_latest_market_data(account.id, CANONICAL_SYMBOL)

    if not tick:
        return {
            "account_id": str(account.id),
            "symbol": CANONICAL_SYMBOL,
            "status": "NO_DATA",
            "is_fresh": False,
            "age_ms": None,
            "bid": None,
            "ask": None,
            "spread": None,
            "point": None,
            "digits": 2,
            "tick_time": None,
            "received_at": None,
        }

    is_fresh, freshness_code, age_ms = market_data_service.evaluate_freshness(tick)

    return {
        "account_id": str(account.id),
        "symbol": CANONICAL_SYMBOL,
        "status": freshness_code,
        "is_fresh": is_fresh,
        "age_ms": age_ms,
        "bid": tick.get("bid"),
        "ask": tick.get("ask"),
        "spread": tick.get("spread"),
        "point": tick.get("point"),
        "digits": tick.get("digits", 2),
        "tick_time": tick.get("tick_time"),
        "tick_volume": tick.get("tick_volume", 0),
        "received_at": tick.get("received_at"),
    }


@router.get("/risk/{account_id}/decision")
async def get_risk_decision(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Authoritative server-side risk gate evaluation for an account.
    Returns deterministic ALLOW or BLOCK with deterministic reason_code.
    Strict tenant isolation: 404 if account does not belong to user.
    """
    account = await _verify_account_ownership(db, account_id, user_id)
    result = await evaluate_risk_gate(db, account.id, CANONICAL_SYMBOL)
    out = result.to_dict()
    out["account_id"] = str(account.id)
    return out


@router.get("/market/chart")
async def get_global_market_chart(
    _user: Annotated[str, Depends(get_current_user)],
    timeframe: str = "M15",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Get live XAUUSD market chart bars for any authenticated operator.
    Does not require a specific trading account to view market pricing.
    """
    norm_tf = timeframe.strip().upper()
    valid_tfs = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}
    if norm_tf not in valid_tfs:
        norm_tf = "M15"

    bars = await market_data_service.get_symbol_closed_bars(CANONICAL_SYMBOL, norm_tf)
    if not bars and norm_tf != "M15":
        bars = await market_data_service.get_symbol_closed_bars(CANONICAL_SYMBOL, "M15")
        if bars:
            norm_tf = "M15"

    if limit and limit > 0 and len(bars) > limit:
        bars = bars[-limit:]

    chart_series = [
        {
            "time": b.get("open_time"),
            "open": float(b.get("open", 0)),
            "high": float(b.get("high", 0)),
            "low": float(b.get("low", 0)),
            "close": float(b.get("close", 0)),
            "volume": float(b.get("volume", 0)),
        }
        for b in bars
    ]

    return {
        "symbol": CANONICAL_SYMBOL,
        "timeframe": norm_tf,
        "count": len(chart_series),
        "bars": chart_series,
        "cached": True,
    }


@router.get("/market/{account_id}/chart")
async def get_market_chart(
    account_id: str,
    user_id: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    timeframe: str = "M15",
    limit: int = 100,
) -> dict[str, Any]:
    """
    Get cached OHLCV market chart bars for an account.
    Returns bars formatted for candlestick/line charts.
    """
    account = await _verify_account_ownership(db, account_id, user_id)
    norm_tf = timeframe.strip().upper()
    valid_tfs = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}
    if norm_tf not in valid_tfs:
        norm_tf = "M15"

    bars = await market_data_service.get_closed_bars(
        account.id, CANONICAL_SYMBOL, norm_tf
    )
    # If requested timeframe has no bars yet, fallback to M15 where live bars are ingested
    if not bars and norm_tf != "M15":
        m15_bars = await market_data_service.get_closed_bars(
            account.id, CANONICAL_SYMBOL, "M15"
        )
        if m15_bars:
            bars = m15_bars
            norm_tf = "M15"

    if limit and limit > 0 and len(bars) > limit:
        bars = bars[-limit:]

    chart_series = []
    for b in bars:
        chart_series.append({
            "time": b.get("open_time"),
            "open": float(b.get("open", 0)),
            "high": float(b.get("high", 0)),
            "low": float(b.get("low", 0)),
            "close": float(b.get("close", 0)),
            "volume": float(b.get("volume", 0)),
        })

    return {
        "account_id": str(account.id),
        "symbol": CANONICAL_SYMBOL,
        "timeframe": norm_tf,
        "count": len(chart_series),
        "bars": chart_series,
        "cached": True,
    }

