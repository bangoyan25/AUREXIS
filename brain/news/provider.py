"""
News Engine provider interface and implementations.

Strict rules:
- News protection is a risk gate: fail-closed.
- If news provider is not configured or unavailable -> NewsState.PROVIDER_UNAVAILABLE / UNKNOWN.
- LiveNewsProvider refuses to fabricate data and returns PROVIDER_UNAVAILABLE until a production provider is approved.
- MockNewsProvider is strictly for deterministic simulation and automated testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class NewsState(StrEnum):
    """Canonical news protection state."""
    CLEAR = "CLEAR"
    PRE_EVENT = "PRE_EVENT"
    IN_EVENT = "IN_EVENT"
    POST_EVENT = "POST_EVENT"
    UNKNOWN = "UNKNOWN"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    STALE = "STALE"


@dataclass(frozen=True)
class CalendarEvent:
    """Normalized economic calendar event."""
    event_id: str
    title: str
    currency: str
    impact: str  # "HIGH", "MEDIUM", "LOW"
    event_time: datetime
    pre_window_minutes: int = 30
    post_window_minutes: int = 30


class NewsProvider(ABC):
    """Abstract interface for macroeconomic news protection providers."""

    @abstractmethod
    def get_news_state(
        self,
        symbol: str = "XAUUSD",
        as_of: datetime | None = None,
    ) -> tuple[NewsState, Sequence[CalendarEvent]]:
        """
        Evaluate news protection state as of a specific UTC timestamp.
        Returns (NewsState, active_or_impending_events).
        """
        ...

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """True if provider produces simulated test data."""
        ...


class LiveNewsProvider(NewsProvider):
    """
    Production News Provider.
    Until a verified production news feed (e.g. ForexFactory, Bloomberg, Refinitiv)
    is formally approved and configured with valid credentials, this provider
    fails closed by returning PROVIDER_UNAVAILABLE.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def get_news_state(
        self,
        symbol: str = "XAUUSD",
        as_of: datetime | None = None,
    ) -> tuple[NewsState, Sequence[CalendarEvent]]:
        # Fail-closed: No production provider configured
        return NewsState.PROVIDER_UNAVAILABLE, ()

    @property
    def is_mock(self) -> bool:
        return False


class MockNewsProvider(NewsProvider):
    """
    Deterministic news provider for local development, simulation, and backtesting.
    Clearly marked as mock data.
    """

    def __init__(self, events: Sequence[CalendarEvent] | None = None) -> None:
        self._events: list[CalendarEvent] = list(events or [])

    def add_event(self, event: CalendarEvent) -> None:
        self._events.append(event)

    def set_events(self, events: Sequence[CalendarEvent]) -> None:
        self._events = list(events)

    def get_news_state(
        self,
        symbol: str = "XAUUSD",
        as_of: datetime | None = None,
    ) -> tuple[NewsState, Sequence[CalendarEvent]]:
        now = as_of or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        relevant_events: list[CalendarEvent] = []
        current_state = NewsState.CLEAR

        for ev in self._events:
            if ev.currency not in ("USD", "ALL"):
                continue
            if ev.impact != "HIGH":
                continue

            ev_time = ev.event_time
            if ev_time.tzinfo is None:
                ev_time = ev_time.replace(tzinfo=UTC)

            pre_start = ev_time - timedelta(minutes=ev.pre_window_minutes)
            post_end = ev_time + timedelta(minutes=ev.post_window_minutes)

            if pre_start <= now < ev_time:
                current_state = NewsState.PRE_EVENT
                relevant_events.append(ev)
            elif now == ev_time or (ev_time <= now <= ev_time + timedelta(minutes=5)):
                current_state = NewsState.IN_EVENT
                relevant_events.append(ev)
            elif ev_time < now <= post_end:
                current_state = NewsState.POST_EVENT
                relevant_events.append(ev)

        return current_state, relevant_events

    @property
    def is_mock(self) -> bool:
        return True
