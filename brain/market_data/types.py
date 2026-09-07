"""
Market data domain types for AUREXIS.

A Tick is the normalized representation of a price update from any broker.
It always carries the canonical AUREXIS symbol (e.g., "XAUUSD"),
not the broker-specific variant (e.g., "XAUUSD.m").

All timestamps are UTC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum


class DataSource(StrEnum):
    """Where the tick data originated."""
    LIVE_BROKER = "LIVE_BROKER"
    REPLAY = "REPLAY"           # Historical replay for testing
    MOCK = "MOCK"               # Test fixture — never treat as live
    UNKNOWN = "UNKNOWN"


class TickStatus(StrEnum):
    """Processing status of a tick."""
    FRESH = "FRESH"       # Within staleness threshold (UNDEFINED — configurable)
    STALE = "STALE"       # Beyond staleness threshold
    INVALID = "INVALID"   # Missing required fields


@dataclass(frozen=True)
class Tick:
    """
    Normalized market tick.

    Units:
    - bid, ask, spread: in quote currency (USD for XAUUSD)
    - volume: tick volume as reported by broker
    - All timestamps in UTC

    The staleness_threshold_seconds field remains None until formally specified.
    When None, any tick is treated as potentially stale — the fail-safe applies.
    """
    symbol: str                          # AUREXIS canonical symbol, e.g. "XAUUSD"
    broker_symbol: str = ""              # Broker-reported symbol, e.g. "XAUUSD.m"
    bid: Decimal = Decimal("0")
    ask: Decimal = Decimal("0")
    tick_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: DataSource = DataSource.UNKNOWN
    sequence_id: int | None = None   # Broker tick sequence number if available
    volume: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.broker_symbol:
            object.__setattr__(self, "broker_symbol", self.symbol)

    @property
    def spread(self) -> Decimal:
        """Bid-ask spread in points/pips."""
        return self.ask - self.bid

    @property
    def mid(self) -> Decimal:
        """Mid price."""
        return (self.bid + self.ask) / Decimal("2")

    def is_mock(self) -> bool:
        return self.source == DataSource.MOCK

    def staleness_seconds(self) -> float:
        """Seconds since this tick was received."""
        now = datetime.now(UTC)
        return (now - self.received_at).total_seconds()


@dataclass(frozen=True)
class MarketDataStatus:
    """
    Current status of the market data feed.

    Used by health checks and the Risk Engine fail-safe.
    If status is not LIVE, no new entries are permitted.
    """
    symbol: str
    is_live: bool
    source: DataSource
    last_tick_at: datetime | None
    staleness_seconds: float | None
    # staleness_threshold: UNDEFINED — will be set when spec is approved
    staleness_threshold_seconds: int | None
    notes: str | None = None

    @property
    def is_fresh(self) -> bool:
        """
        Returns True only if data is live and within the staleness threshold.

        If staleness_threshold_seconds is None (UNDEFINED), returns False — fail safe.
        If last_tick_at is None, returns False.
        """
        if not self.is_live:
            return False
        if self.last_tick_at is None:
            return False
        if self.staleness_threshold_seconds is None:
            return False  # Threshold UNDEFINED → assume not fresh (fail safe)
        if self.staleness_seconds is None:
            return False
        return self.staleness_seconds <= self.staleness_threshold_seconds



@dataclass(frozen=True)
class Bar:
    """Canonical OHLCV bar for multi-timeframe analysis."""
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal = Decimal("0")
    is_closed: bool = True

    @property
    def open(self) -> Decimal:
        return self.open_price

    @property
    def high(self) -> Decimal:
        return self.high_price

    @property
    def low(self) -> Decimal:
        return self.low_price

    @property
    def close(self) -> Decimal:
        return self.close_price

    @property
    def timestamp(self) -> datetime:
        return self.close_time

