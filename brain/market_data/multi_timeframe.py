"""
Multi-Timeframe Market Data Manager — Stage C.

Strict separation of M5, M15, H1 bar streams with:
- Causal chronological ingestion.
- No lookahead bias: bar closed only when next bucket arrives.
- Tick validation, staleness, and spread tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from backend.core.logging import get_logger
from brain.bar_builder import BarBuilder
from brain.market_data.types import Bar, Tick

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger("brain.market_data.multi_timeframe")

DEFAULT_TIMEFRAMES: tuple[str, ...] = ("M5", "M15", "H1")


@dataclass(frozen=True)
class TickValidationResult:
    """Validation outcome for an incoming tick."""
    is_valid: bool
    error_message: str | None = None


@dataclass(frozen=True)
class TimeframeUpdateResult:
    """Outcome of processing a tick across all timeframes."""
    tick: Tick
    newly_closed_bars: dict[str, Bar] = field(default_factory=dict)


class MultiTimeframeBarManager:
    """
    Coordinates multi-timeframe bar aggregation from normalized tick streams.
    Guarantees independent BarBuilder instances for each timeframe.
    """

    def __init__(
        self,
        symbol: str = "XAUUSD",
        timeframes: Sequence[str] = DEFAULT_TIMEFRAMES,
        max_spread_usd: Decimal = Decimal("2.00"),
        staleness_threshold_seconds: float = 10.0,
    ) -> None:
        self.symbol = symbol
        self.timeframes = tuple(timeframes)
        self.max_spread_usd = max_spread_usd
        self.staleness_threshold_seconds = staleness_threshold_seconds
        self._builders: dict[str, BarBuilder] = {
            tf: BarBuilder(symbol=symbol, timeframe=tf)
            for tf in self.timeframes
        }
        self._last_tick: Tick | None = None
        self._tick_count: int = 0

    @property
    def last_tick(self) -> Tick | None:
        return self._last_tick

    @property
    def tick_count(self) -> int:
        return self._tick_count

    def validate_tick(self, tick: Tick) -> TickValidationResult:
        if tick.symbol != self.symbol:
            return TickValidationResult(False, f"Symbol mismatch: {tick.symbol}")
        if tick.bid <= Decimal("0") or tick.ask <= Decimal("0"):
            return TickValidationResult(False, f"Non-positive price: {tick.bid}/{tick.ask}")
        if tick.bid > tick.ask:
            return TickValidationResult(False, f"Crossed spread: bid={tick.bid} > ask={tick.ask}")
        if self._last_tick is not None and tick.tick_time < self._last_tick.tick_time:
            return TickValidationResult(False, f"Out of order tick: {tick.tick_time} < {self._last_tick.tick_time}")
        return TickValidationResult(True)

    def is_stale(self, as_of: datetime | None = None) -> bool:
        if self._last_tick is None:
            return True
        now = as_of or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        tick_time = self._last_tick.tick_time
        if tick_time.tzinfo is None:
            tick_time = tick_time.replace(tzinfo=UTC)
        return (now - tick_time).total_seconds() > self.staleness_threshold_seconds

    def current_spread(self) -> Decimal | None:
        return self._last_tick.spread if self._last_tick else None

    def is_spread_acceptable(self) -> bool:
        spread = self.current_spread()
        return bool(spread is not None and spread <= self.max_spread_usd)

    def ingest_tick(self, tick: Tick) -> TimeframeUpdateResult:
        val = self.validate_tick(tick)
        if not val.is_valid:
            raise ValueError(f"Tick invalid: {val.error_message}")
        self._last_tick = tick
        self._tick_count += 1
        newly_closed: dict[str, Bar] = {}
        for tf, builder in self._builders.items():
            b = builder.process_tick(tick)
            if b is not None:
                newly_closed[tf] = b
        return TimeframeUpdateResult(tick=tick, newly_closed_bars=newly_closed)

    def get_closed_bars(self, timeframe: str) -> list[Bar]:
        builder = self._builders.get(timeframe)
        if builder is None:
            raise ValueError(f"Timeframe {timeframe} not tracked")
        return builder.closed_bars

    def get_latest_closed_bar(self, timeframe: str) -> Bar | None:
        bars = self.get_closed_bars(timeframe)
        return bars[-1] if bars else None

