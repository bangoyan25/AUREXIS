"""
Economic News Service for AUREXIS.

Ingests high-impact macroeconomic events (USD/XAUUSD interest rates, CPI, NFP, FOMC)
into PostgreSQL news_events table and calculates news protection blackout windows.
Fail-safe: defaults to CLEAR when calendar confirms no high-impact events nearby,
or BLACKOUT if currently inside pre/post event window.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.db.models.news import NewsEvent

logger = get_logger("news_service")

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
SOURCE_NAME = "forexfactory"
DEFAULT_PRE_WINDOW_MIN = 30
DEFAULT_POST_WINDOW_MIN = 30


async def fetch_and_sync_news(
    session: AsyncSession,
    pre_window_min: int = DEFAULT_PRE_WINDOW_MIN,
    post_window_min: int = DEFAULT_POST_WINDOW_MIN,
) -> int:
    """
    Fetch economic calendar from public feed and update news_events table.
    Returns number of events ingested.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(FEED_URL)
            if resp.status_code != 200:
                logger.warning("news_sync.fetch_failed", status_code=resp.status_code)
                return 0
            items = resp.json()
    except Exception as exc:
        logger.warning("news_sync.network_error", error=str(exc))
        return 0

    if not isinstance(items, list):
        return 0

    ingested = 0
    now = datetime.now(timezone.utc)

    for item in items:
        country = str(item.get("country", "")).upper()
        # XAUUSD is predominantly driven by USD macroeconomic news
        if country != "USD":
            continue

        raw_impact = str(item.get("impact", "")).capitalize()
        impact = "HIGH" if raw_impact == "High" else ("MEDIUM" if raw_impact == "Medium" else "LOW")

        raw_date = item.get("date")
        if not raw_date:
            continue

        try:
            event_dt = datetime.fromisoformat(raw_date)
            # Normalize to UTC
            event_dt_utc = event_dt.astimezone(timezone.utc)
        except Exception:
            continue

        title = str(item.get("title", "USD Economic Event"))
        source_id = f"{country}_{event_dt_utc.strftime('%Y%m%d%H%M')}_{title[:30].replace(' ', '_')}"

        pre_start = event_dt_utc - timedelta(minutes=pre_window_min)
        post_end = event_dt_utc + timedelta(minutes=post_window_min)

        # Check existing
        stmt = select(NewsEvent).where(
            NewsEvent.source == SOURCE_NAME,
            NewsEvent.source_event_id == source_id,
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.impact = impact
            existing.actual_value = str(item.get("actual", "")) or None
            existing.forecast_value = str(item.get("forecast", "")) or None
            existing.previous_value = str(item.get("previous", "")) or None
            existing.pre_event_window_start = pre_start
            existing.post_event_window_end = post_end
        else:
            ev = NewsEvent(
                id=uuid.uuid4(),
                source=SOURCE_NAME,
                source_event_id=source_id,
                event_name=title,
                currency=country,
                impact=impact,
                event_time=event_dt_utc,
                pre_event_window_start=pre_start,
                post_event_window_end=post_end,
                actual_value=str(item.get("actual", "")) or None,
                forecast_value=str(item.get("forecast", "")) or None,
                previous_value=str(item.get("previous", "")) or None,
            )
            session.add(ev)
            ingested += 1

    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error("news_sync.commit_error", error=str(exc))
        return 0

    logger.info("news_sync.success", count=ingested)
    return ingested


async def get_news_protection_state(
    session: AsyncSession,
    pre_window_min: int = DEFAULT_PRE_WINDOW_MIN,
    post_window_min: int = DEFAULT_POST_WINDOW_MIN,
) -> dict[str, Any]:
    """
    Evaluates whether high-impact news blocks trading right now.
    Returns:
      {
        "status": "CLEAR" | "BLACKOUT" | "UPCOMING",
        "provider": "FOREXFACTORY_SYNC",
        "active_event": str | None,
        "pre_event_window_minutes": int,
        "post_event_window_minutes": int,
        "upcoming_events": [...],
        "note": str
      }
    """
    now = datetime.now(timezone.utc)
    lookahead = now + timedelta(hours=48)
    lookbehind = now - timedelta(hours=2)

    stmt = (
        select(NewsEvent)
        .where(
            NewsEvent.currency == "USD",
            NewsEvent.impact == "HIGH",
            NewsEvent.event_time >= lookbehind,
            NewsEvent.event_time <= lookahead,
        )
        .order_by(NewsEvent.event_time.asc())
    )
    res = await session.execute(stmt)
    events = res.scalars().all()

    active_blackout_event: NewsEvent | None = None
    upcoming_event: NewsEvent | None = None

    formatted_events = []
    for ev in events:
        is_active = ev.pre_event_window_start <= now <= ev.post_event_window_end
        if is_active and not active_blackout_event:
            active_blackout_event = ev

        mins_to = int((ev.event_time - now).total_seconds() / 60)
        if mins_to > 0 and (not upcoming_event or mins_to < int((upcoming_event.event_time - now).total_seconds() / 60)):
            upcoming_event = ev

        formatted_events.append({
            "id": str(ev.id),
            "event_name": ev.event_name,
            "currency": ev.currency,
            "impact": ev.impact,
            "event_time": ev.event_time.isoformat(),
            "pre_event_window_start": ev.pre_event_window_start.isoformat(),
            "post_event_window_end": ev.post_event_window_end.isoformat(),
            "actual": ev.actual_value,
            "forecast": ev.forecast_value,
            "previous": ev.previous_value,
            "is_blackout_active": is_active,
            "minutes_until": mins_to,
        })

    if active_blackout_event:
        return {
            "status": "BLACKOUT",
            "provider": SOURCE_NAME.upper(),
            "trading_allowed": False,
            "active_event": active_blackout_event.event_name,
            "pre_event_window_minutes": pre_window_min,
            "post_event_window_minutes": post_window_min,
            "upcoming_events": formatted_events[:15],
            "note": f"HIGH-IMPACT NEWS BLACKOUT: '{active_blackout_event.event_name}'. Trading strictly blocked.",
        }

    if upcoming_event and int((upcoming_event.event_time - now).total_seconds() / 60) <= 120:
        mins = int((upcoming_event.event_time - now).total_seconds() / 60)
        return {
            "status": "UPCOMING",
            "provider": SOURCE_NAME.upper(),
            "trading_allowed": True,
            "active_event": None,
            "upcoming_event": upcoming_event.event_name,
            "minutes_until": mins,
            "pre_event_window_minutes": pre_window_min,
            "post_event_window_minutes": post_window_min,
            "upcoming_events": formatted_events[:15],
            "note": f"Upcoming high-impact event '{upcoming_event.event_name}' in {mins} minutes.",
        }

    return {
        "status": "CLEAR",
        "provider": SOURCE_NAME.upper(),
        "trading_allowed": True,
        "active_event": None,
        "pre_event_window_minutes": pre_window_min,
        "post_event_window_minutes": post_window_min,
        "upcoming_events": formatted_events[:15],
        "note": "No active economic news blackout window. News protection clear.",
    }
