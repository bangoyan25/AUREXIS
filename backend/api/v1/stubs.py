"""
Stub API endpoints for domains not yet implemented.

All return explicit NOT_CONFIGURED or EMPTY states.
No fake trading data. No invented production values.

Domains: risk, brain, market, signals, positions, execution,
         news, performance, backtest.

These endpoints establish the REST boundary so the frontend
can connect and display correct states rather than network errors.
Each will be replaced by real implementations as backend domains are built.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from backend.api.deps import get_current_user

router = APIRouter(tags=["domain-stubs"])

_NC = "NOT_CONFIGURED"
_NOTE_BRAIN = (
    "Brain strategy parameters are UNDEFINED. "
    "Signal generation will not occur until parameters are formally approved."
)
_NOTE_RISK = (
    "Risk Engine parameters (daily loss limit, max drawdown, position sizing) "
    "are UNDEFINED. Trading is blocked until parameters are formally approved."
)
_NOTE_NEWS = (
    "News provider is UNDEFINED. "
    "News protection state cannot be determined. Fail-safe: UNKNOWN."
)
_NOTE_MARKET = (
    "Market data provider is UNDEFINED. "
    "No live tick data is available."
)


# ── Risk ──────────────────────────────────────────────────────────────────

@router.get("/risk/{account_id}")
async def get_risk_state(
    account_id: str,
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "risk_state": _NC,
        "trading_allowed": False,
        "block_reason": "MISSING_PARAMETERS",
        "note": _NOTE_RISK,
        "parameters": {
            "daily_loss_limit_usd": None,
            "max_drawdown_usd": None,
            "max_open_positions": None,
            "risk_per_trade_pct": None,
            "profit_lock_formula": "PCT_RETRACE",
            "profit_lock_threshold_usd": "10.00",
            "profit_lock_floor_pct": "0.30",
            "drawdown_reference": "LIFETIME_HWM",
            "daily_reset_timezone": "UTC",
        },
    }


# ── Brain ─────────────────────────────────────────────────────────────────

@router.get("/brain/{account_id}")
async def get_brain_state(
    account_id: str,
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "account_id": account_id,
        "brain_state": _NC,
        "strategy_id": "AUREXIS_CORE",
        "strategy_version": "AUREXIS-STRAT-1.0.0",
        "regime": _NC,
        "structure": _NC,
        "trend": _NC,
        "momentum": _NC,
        "volatility": _NC,
        "active_setup": _NC,
        "confidence": None,
        "live_trading_enabled": False,
        "note": _NOTE_BRAIN,
    }




# ── Market data ───────────────────────────────────────────────────────────

@router.get("/market/tick")
async def get_market_tick(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "symbol": "XAUUSD",
        "status": _NC,
        "bid": None,
        "ask": None,
        "spread_pips": None,
        "note": _NOTE_MARKET,
    }


# ── Signals ───────────────────────────────────────────────────────────────

@router.get("/signals")
async def list_signals(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "status": _NC,
        "signals": [],
        "note": "No signals generated — Brain is NOT_CONFIGURED.",
    }


# ── Positions ─────────────────────────────────────────────────────────────

@router.get("/positions")
async def list_positions(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "status": "EMPTY",
        "positions": [],
        "note": "No live positions. MT5 not connected.",
    }


# ── Execution ─────────────────────────────────────────────────────────────

@router.get("/execution")
async def list_commands(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "status": "EMPTY",
        "commands": [],
        "note": "No execution commands. MT5 not connected and Brain NOT_CONFIGURED.",
    }


# ── News ──────────────────────────────────────────────────────────────────

@router.get("/news")
async def get_news_state(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "status": "UNKNOWN",
        "provider": None,
        "upcoming_events": [],
        "pre_event_window_minutes": 30,
        "post_event_window_minutes": 30,
        "note": _NOTE_NEWS,
    }


# ── Performance ───────────────────────────────────────────────────────────

@router.get("/performance")
async def get_performance(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "status": "EMPTY",
        "total_trades": 0,
        "win_rate": None,
        "total_pnl_usd": "0.00",
        "daily_pnl": [],
        "note": "No trade history available.",
    }


# ── Backtest ──────────────────────────────────────────────────────────────

@router.get("/backtest")
async def get_backtest(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    return {
        "status": _NC,
        "note": (
            "Backtest engine is NOT_CONFIGURED. "
            "Strategy parameters must be finalized before backtesting."
        ),
        "results": [],
    }
