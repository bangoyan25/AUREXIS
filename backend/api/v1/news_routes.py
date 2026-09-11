"""
News Protection & Macroeconomic Calendar API.

Provides real-time visibility into high-impact economic news releases
and calculated pre/post blackout protection windows for XAUUSD trading.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user
from backend.db.session import get_db
from backend.services import news_service

router = APIRouter(prefix="/news", tags=["news-engine"])


@router.get("")
async def get_news_state(
    _user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Get current macroeconomic news protection state, active blackout status,
    and upcoming high-impact economic events.
    """
    return await news_service.get_news_protection_state(db)


@router.post("/sync")
async def trigger_news_sync(
    _user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Trigger on-demand synchronization of the economic calendar feed.
    """
    ingested = await news_service.fetch_and_sync_news(db)
    state = await news_service.get_news_protection_state(db)
    return {
        "status": "OK",
        "ingested_events": ingested,
        "current_news_state": state["status"],
        "note": f"Synchronized {ingested} economic calendar events from external feed.",
    }
