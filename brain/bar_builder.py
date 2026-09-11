"""
Bar Builder — tick aggregator into OHLCV bars.

Takes stream of normalized Ticks and accumulates into closed Bars.
Guarantees:
- Discrete timeframe buckets (e.g. 60s for M1, 300s for M5)
- Bar closure semantics: a bar is marked is_closed=True only when a tick arrives in a subsequent bucket
- Preserves accurate Open, High, Low, Close, and Volume (sum of tick volume or tick count)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from brain.market_data.types import Bar, Tick


class BarBuilder:
    """Aggregates Ticks into OHLCV bars for a specific timeframe."""

    TIMEFRAME_SECONDS: dict[str, int] = {
        "M1": 60,
        "M5": 300,
        "M15": 900,
        "M30": 1800,
        "H1": 3600,
        "H4": 14400,
        "D1": 86400,
    }

    def __init__(self, symbol: str, timeframe: str = "M1") -> None:
        if timeframe not in self.TIMEFRAME_SECONDS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        self.symbol = symbol
        self.timeframe = timeframe
        self.interval_seconds = self.TIMEFRAME_SECONDS[timeframe]

        self._current_bar_start: datetime | None = None
        self._open: Decimal | None = None
        self._high: Decimal | None = None
        self._low: Decimal | None = None
        self._close: Decimal | None = None
        self._volume: Decimal = Decimal("0")
        self._closed_bars: list[Bar] = []

    @property
    def closed_bars(self) -> list[Bar]:
        """All closed bars produced so far, in chronological order."""
        return list(self._closed_bars)

    def seed_closed_bars(self, bars: list[Bar]) -> None:
        """
        Seed or update historical closed bars.
        Bars must be chronologically ordered and is_closed=True.
        Deduplicates by open_time and preserves ascending chronological order.
        """
        existing_by_time = {b.open_time: b for b in self._closed_bars}
        for b in bars:
            if not b.is_closed:
                continue
            existing_by_time[b.open_time] = b
        self._closed_bars = sorted(existing_by_time.values(), key=lambda b: b.open_time)
        if len(self._closed_bars) > 300:
            self._closed_bars = self._closed_bars[-300:]


    def _get_bucket_start(self, dt: datetime) -> datetime:
        """Floor datetime to the timeframe interval boundary."""
        epoch = dt.timestamp()
        bucket_epoch = (int(epoch) // self.interval_seconds) * self.interval_seconds
        return datetime.fromtimestamp(bucket_epoch, tz=UTC)

    def process_tick(self, tick: Tick) -> Bar | None:
        """
        Incorporate a new tick.
        If this tick crosses into a new interval, close the previous bar and return it.
        Otherwise, update the current running bar and return None.
        """
        price = tick.mid  # Use normalized mid price for bar generation
        volume = tick.volume if tick.volume is not None else Decimal("1")
        bucket_start = self._get_bucket_start(tick.tick_time)

        closed_bar: Bar | None = None

        if self._current_bar_start is None:
            # First tick initializes the current bar
            self._current_bar_start = bucket_start
            self._open = price
            self._high = price
            self._low = price
            self._close = price
            self._volume = volume
        elif bucket_start > self._current_bar_start:
            # Tick crossed boundary: close current bar
            bar_end = self._current_bar_start + timedelta(seconds=self.interval_seconds)
            closed_bar = Bar(
                symbol=self.symbol,
                timeframe=self.timeframe,
                open_time=self._current_bar_start,
                close_time=bar_end,
                open_price=self._open,  # type: ignore[arg-type]
                high_price=self._high,  # type: ignore[arg-type]
                low_price=self._low,    # type: ignore[arg-type]
                close_price=self._close,  # type: ignore[arg-type]
                volume=self._volume,
                is_closed=True,
            )
            self._closed_bars.append(closed_bar)

            # Start new running bar
            self._current_bar_start = bucket_start
            self._open = price
            self._high = price
            self._low = price
            self._close = price
            self._volume = volume
        else:
            # Ongoing bar in the same bucket
            if price > self._high:  # type: ignore[operator]
                self._high = price
            if price < self._low:  # type: ignore[operator]
                self._low = price
            self._close = price
            self._volume += volume

        return closed_bar
