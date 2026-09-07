"""Tests for MultiTimeframeBarManager — Stage C."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from brain.market_data.multi_timeframe import DEFAULT_TIMEFRAMES, MultiTimeframeBarManager
from brain.market_data.types import DataSource, Tick


def make_tick(
    bid: Decimal = Decimal("2700.00"),
    ask: Decimal = Decimal("2700.30"),
    tick_time: datetime | None = None,
    symbol: str = "XAUUSD",
) -> Tick:
    t = tick_time or datetime.now(UTC)
    return Tick(symbol=symbol, bid=bid, ask=ask, tick_time=t, received_at=t, source=DataSource.MOCK)


def test_creates_builders_for_each_timeframe() -> None:
    mgr = MultiTimeframeBarManager(symbol="XAUUSD", timeframes=("M5", "M15", "H1"))
    assert set(mgr.timeframes) == {"M5", "M15", "H1"}


def test_default_timeframes() -> None:
    mgr = MultiTimeframeBarManager()
    assert set(mgr.timeframes) == set(DEFAULT_TIMEFRAMES)


def test_validation_passes_for_valid_tick() -> None:
    mgr = MultiTimeframeBarManager()
    tick = make_tick()
    result = mgr.validate_tick(tick)
    assert result.is_valid


def test_validation_fails_nonpositive_bid() -> None:
    mgr = MultiTimeframeBarManager()
    tick = make_tick(bid=Decimal("0"), ask=Decimal("2700.30"))
    result = mgr.validate_tick(tick)
    assert not result.is_valid
    assert "Non-positive" in (result.error_message or "")


def test_validation_fails_crossed_spread() -> None:
    mgr = MultiTimeframeBarManager()
    tick = make_tick(bid=Decimal("2701.00"), ask=Decimal("2700.00"))
    result = mgr.validate_tick(tick)
    assert not result.is_valid
    assert "Crossed" in (result.error_message or "")


def test_validation_fails_symbol_mismatch() -> None:
    mgr = MultiTimeframeBarManager(symbol="XAUUSD")
    tick = make_tick(symbol="EURUSD")
    result = mgr.validate_tick(tick)
    assert not result.is_valid


def test_validation_fails_out_of_order_tick() -> None:
    mgr = MultiTimeframeBarManager()
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 1, 1, 9, 59, 0, tzinfo=UTC)
    mgr.ingest_tick(make_tick(tick_time=t0))
    with pytest.raises(ValueError, match="Out of order"):
        mgr.ingest_tick(make_tick(tick_time=t1))


def test_ingest_invalid_tick_raises() -> None:
    mgr = MultiTimeframeBarManager()
    tick = make_tick(bid=Decimal("0"))
    with pytest.raises(ValueError):
        mgr.ingest_tick(tick)


def test_stale_when_no_tick() -> None:
    mgr = MultiTimeframeBarManager()
    assert mgr.is_stale()


def test_not_stale_with_fresh_tick() -> None:
    mgr = MultiTimeframeBarManager(staleness_threshold_seconds=10.0)
    tick = make_tick(tick_time=datetime.now(UTC))
    mgr.ingest_tick(tick)
    assert not mgr.is_stale(as_of=datetime.now(UTC) + timedelta(seconds=5))


def test_stale_with_old_tick() -> None:
    mgr = MultiTimeframeBarManager(staleness_threshold_seconds=10.0)
    old_time = datetime.now(UTC) - timedelta(seconds=60)
    mgr.ingest_tick(make_tick(tick_time=old_time))
    assert mgr.is_stale(as_of=datetime.now(UTC))


def test_no_spread_before_any_tick() -> None:
    mgr = MultiTimeframeBarManager()
    assert mgr.current_spread() is None
    assert not mgr.is_spread_acceptable()


def test_spread_acceptable_within_limit() -> None:
    mgr = MultiTimeframeBarManager(max_spread_usd=Decimal("2.00"))
    mgr.ingest_tick(make_tick(bid=Decimal("2700.00"), ask=Decimal("2700.50")))
    assert mgr.current_spread() == Decimal("0.50")
    assert mgr.is_spread_acceptable()


def test_spread_rejected_over_limit() -> None:
    mgr = MultiTimeframeBarManager(max_spread_usd=Decimal("0.40"))
    mgr.ingest_tick(make_tick(bid=Decimal("2700.00"), ask=Decimal("2700.50")))
    assert not mgr.is_spread_acceptable()


def test_no_closed_bars_initially() -> None:
    mgr = MultiTimeframeBarManager()
    for tf in mgr.timeframes:
        assert mgr.get_closed_bars(tf) == []


def test_m5_bar_closes_after_6_minutes() -> None:
    mgr = MultiTimeframeBarManager(timeframes=("M5",))
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    for i in range(7):
        mgr.ingest_tick(make_tick(tick_time=t0 + timedelta(minutes=i)))
    bars = mgr.get_closed_bars("M5")
    assert len(bars) >= 1
    for bar in bars:
        assert bar.is_closed


def test_timeframes_are_independent() -> None:
    mgr = MultiTimeframeBarManager(timeframes=("M5", "H1"))
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    for i in range(75):
        mgr.ingest_tick(make_tick(tick_time=t0 + timedelta(minutes=i)))
    m5_bars = mgr.get_closed_bars("M5")
    h1_bars = mgr.get_closed_bars("H1")
    assert len(m5_bars) > len(h1_bars)


def test_unknown_timeframe_raises() -> None:
    mgr = MultiTimeframeBarManager(timeframes=("M5",))
    with pytest.raises(ValueError):
        mgr.get_closed_bars("D1")


def test_get_latest_closed_bar_returns_none_when_empty() -> None:
    mgr = MultiTimeframeBarManager()
    assert mgr.get_latest_closed_bar("M5") is None


def test_tick_count_increments() -> None:
    mgr = MultiTimeframeBarManager()
    for i in range(5):
        t = datetime(2026, 1, 1, 12, 0, i, tzinfo=UTC)
        mgr.ingest_tick(make_tick(tick_time=t))
    assert mgr.tick_count == 5


def test_all_closed_bars_have_is_closed_true() -> None:
    mgr = MultiTimeframeBarManager(timeframes=("M5", "M15"))
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    for i in range(20):
        mgr.ingest_tick(make_tick(tick_time=t0 + timedelta(minutes=i)))
    for tf in ("M5", "M15"):
        for bar in mgr.get_closed_bars(tf):
            assert bar.is_closed, f"Bar in {tf} not closed"


def test_ingest_returns_newly_closed_bar() -> None:
    mgr = MultiTimeframeBarManager(timeframes=("M5",))
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    # Fill ticks in first bucket (minutes 0-4)
    for i in range(5):
        mgr.ingest_tick(make_tick(tick_time=t0 + timedelta(minutes=i)))
    # Tick at minute 5 crosses into next M5 bucket → closes previous bar
    result = mgr.ingest_tick(make_tick(tick_time=t0 + timedelta(minutes=5)))
    assert "M5" in result.newly_closed_bars
    assert result.newly_closed_bars["M5"].is_closed
