"""
Market data provider interface.

All market data providers implement this protocol.
The application never receives ticks directly from a broker object —
it always goes through a normalized provider implementation.

If no real provider is configured, MockMarketDataProvider is used in development.
MockMarketDataProvider must never be mistaken for live data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from brain.market_data.types import DataSource, MarketDataStatus, Tick

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class MarketDataProvider(ABC):
    """
    Abstract base class for all AUREXIS market data providers.

    Implementations must:
    - Normalize broker symbols to AUREXIS canonical symbols
    - Report data freshness accurately
    - Never present stale or mock data as live
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the connection."""
        ...

    @abstractmethod
    def tick_stream(self, symbol: str) -> AsyncIterator[Tick]:
        """
        Yield normalized ticks for the given canonical symbol.
        Raises StopAsyncIteration when the stream ends.
        """
        ...

    @abstractmethod
    async def get_status(self, symbol: str) -> MarketDataStatus:
        """Return current data feed status for the given symbol."""
        ...

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """True if this provider returns simulated data."""
        ...


class MockMarketDataProvider(MarketDataProvider):
    """
    Development mock market data provider.

    Returns clearly labeled test fixtures.
    MUST NEVER be used in production mode.
    MUST NEVER present data as live.
    """

    def __init__(self) -> None:
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def tick_stream(self, symbol: str) -> AsyncIterator[Tick]:
        """
        Yields a single static mock tick and stops.
        Tests that need continuous streams should subclass or mock this method.
        """
        yield Tick(
            symbol=symbol,
            broker_symbol=f"{symbol}.MOCK",
            bid=Decimal("2000.00"),
            ask=Decimal("2000.50"),
            tick_time=datetime.now(UTC),
            received_at=datetime.now(UTC),
            source=DataSource.MOCK,
        )

    async def get_status(self, symbol: str) -> MarketDataStatus:
        return MarketDataStatus(
            symbol=symbol,
            is_live=False,
            source=DataSource.MOCK,
            last_tick_at=None,
            staleness_seconds=None,
            staleness_threshold_seconds=None,
            notes="MockMarketDataProvider — no live data. For development only.",
        )

    @property
    def is_mock(self) -> bool:
        return True
