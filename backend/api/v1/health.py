"""
AUREXIS health check endpoint.

Reports the operational state of each system component.
Distinguishes IMPLEMENTED/CONFIGURED/NOT_CONFIGURED/UNHEALTHY.
Never reports fake healthy status.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis import check_redis_health

router = APIRouter(tags=["health"])
logger = get_logger("health")


async def _check_postgres() -> dict[str, object]:
    """Attempt a lightweight database query."""
    try:
        from sqlalchemy import text

        from backend.db.session import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def _risk_engine_status() -> dict[str, object]:
    """
    Risk Engine configuration status.
    Returns NOT_CONFIGURED if required parameters are undefined.
    """
    required = {
        "daily_loss_limit": settings.RISK_DAILY_LOSS_LIMIT_USD,
        "max_drawdown": settings.RISK_MAX_DRAWDOWN_USD,
        "profit_lock_formula": settings.RISK_PROFIT_LOCK_FORMULA,
        "max_open_positions": settings.RISK_MAX_OPEN_POSITIONS,
        "default_position_size": settings.RISK_DEFAULT_POSITION_SIZE_LOTS,
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        return {
            "status": "NOT_CONFIGURED",
            "missing_parameters": missing,
            "note": "Risk Engine requires approved production parameters before trading.",
        }
    return {"status": "CONFIGURED"}


def _market_data_status() -> dict[str, object]:
    if not settings.MARKET_DATA_PROVIDER:
        return {
            "status": "NOT_CONFIGURED",
            "note": "Market data provider is UNDEFINED — awaiting specification.",
        }
    return {"status": "CONFIGURED", "provider": settings.MARKET_DATA_PROVIDER}


def _news_status() -> dict[str, object]:
    if not settings.NEWS_PROVIDER:
        return {
            "status": "NOT_CONFIGURED",
            "note": "News provider is UNDEFINED — awaiting specification.",
        }
    return {"status": "CONFIGURED", "provider": settings.NEWS_PROVIDER}


def _brain_status() -> dict[str, object]:
    """
    Brain is structurally present but strategy formulas are UNDEFINED.
    Signal generation will return NOT_CONFIGURED until strategy is approved.
    """
    return {
        "status": "NOT_CONFIGURED",
        "note": (
            "Strategy parameters (indicators, entry/exit rules, signal scoring, "
            "market structure/breakout/fakeout definitions) are UNDEFINED. "
            "Brain is implemented structurally but will not generate live signals."
        ),
    }


def _mt5_status() -> dict[str, object]:
    """MT5 agents — no agents registered yet."""
    return {
        "status": "NO_AGENTS",
        "connected_agents": 0,
        "note": "No MT5 EA connections registered.",
    }


@router.get("/health")
async def health() -> dict[str, Any]:
    """
    System health endpoint.

    Returns the operational status of every AUREXIS component.
    Never returns fake healthy status.
    """
    start = time.perf_counter()

    postgres = await _check_postgres()
    redis = await check_redis_health()

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

    overall = (
        "healthy"
        if postgres["status"] == "healthy" and redis["status"] == "healthy"
        else "degraded"
    )

    result = {
        "status": overall,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "check_duration_ms": elapsed_ms,
        "components": {
            "backend": {"status": "healthy"},
            "database": postgres,
            "redis": redis,
            "brain": _brain_status(),
            "risk_engine": _risk_engine_status(),
            "market_data": _market_data_status(),
            "news": _news_status(),
            "mt5": _mt5_status(),
        },
    }

    logger.info(
        "health.check",
        overall=overall,
        postgres=postgres["status"],
        redis=redis["status"],
        duration_ms=elapsed_ms,
    )

    return result


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Kubernetes-style liveness probe — returns 200 if process is alive."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> dict[str, Any]:
    """
    Readiness probe — returns 200 only if DB and Redis are reachable.
    503 is returned by FastAPI automatically if this raises HTTPException.
    """
    from fastapi import HTTPException

    postgres = await _check_postgres()
    redis = await check_redis_health()

    if postgres["status"] != "healthy" or redis["status"] != "healthy":
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "database": postgres,
                "redis": redis,
            },
        )
    return {"status": "ready"}
