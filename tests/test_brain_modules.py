"""
Unit tests for Brain modules: BarBuilder, Indicators, Structure, Regime, and Scorer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from brain.bar_builder import BarBuilder
from brain.indicators import calculate_atr, calculate_ema, calculate_rsi, calculate_sma
from brain.market_data.types import Bar, Tick
from brain.regime import classify_regime
from brain.structure import analyze_structure, detect_swing_points


def make_test_bar(index: int, open_p: str, high_p: str, low_p: str, close_p: str) -> Bar:
    base_time = datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC)
    return Bar(
        symbol="XAUUSD",
        timeframe="M1",
        open_time=base_time + timedelta(minutes=index),
        close_time=base_time + timedelta(minutes=index + 1),
        open_price=Decimal(open_p),
        high_price=Decimal(high_p),
        low_price=Decimal(low_p),
        close_price=Decimal(close_p),
        volume=Decimal("100"),
        is_closed=True,
    )


def test_bar_builder_aggregates_ticks_and_closes():
    builder = BarBuilder(symbol="XAUUSD", timeframe="M1")
    t0 = datetime(2026, 9, 6, 12, 0, 10, tzinfo=UTC)
    t1 = datetime(2026, 9, 6, 12, 0, 45, tzinfo=UTC)
    t2 = datetime(2026, 9, 6, 12, 1, 5, tzinfo=UTC)

    tick0 = Tick(symbol="XAUUSD", broker_symbol="XAUUSD", bid=Decimal("2500.00"), ask=Decimal("2500.20"), tick_time=t0, received_at=t0)
    tick1 = Tick(symbol="XAUUSD", broker_symbol="XAUUSD", bid=Decimal("2502.00"), ask=Decimal("2502.20"), tick_time=t1, received_at=t1)
    tick2 = Tick(symbol="XAUUSD", broker_symbol="XAUUSD", bid=Decimal("2499.00"), ask=Decimal("2499.20"), tick_time=t2, received_at=t2)

    bar0 = builder.process_tick(tick0)
    assert bar0 is None

    bar1 = builder.process_tick(tick1)
    assert bar1 is None

    closed_bar = builder.process_tick(tick2)
    assert closed_bar is not None
    assert closed_bar.is_closed is True
    assert closed_bar.open_price == Decimal("2500.10")
    assert closed_bar.high_price == Decimal("2502.10")
    assert closed_bar.low_price == Decimal("2500.10")
    assert closed_bar.close_price == Decimal("2502.10")


def test_indicators_sma_and_ema():
    bars = [make_test_bar(i, "10", "15", "5", str(10 + i)) for i in range(10)]
    sma5 = calculate_sma(bars, 5)
    assert sma5 is not None
    expected_sma5 = (Decimal("15") + Decimal("16") + Decimal("17") + Decimal("18") + Decimal("19")) / Decimal("5")
    assert sma5 == expected_sma5

    ema5 = calculate_ema(bars, 5)
    assert ema5 is not None
    assert isinstance(ema5, Decimal)


def test_indicators_atr_and_rsi():
    bars = [make_test_bar(i, "100", "110", "90", "100") for i in range(20)]
    atr14 = calculate_atr(bars, 14)
    assert atr14 is not None
    assert atr14 == Decimal("20")

    rsi14 = calculate_rsi(bars, 14)
    assert rsi14 is not None


def test_structure_detect_swing_points():
    # Construct sequence with a clear swing high in the middle
    bars = [
        make_test_bar(0, "10", "12", "9", "11"),
        make_test_bar(1, "11", "14", "10", "13"),
        make_test_bar(2, "13", "20", "12", "18"),  # Peak at 20
        make_test_bar(3, "18", "16", "11", "14"),
        make_test_bar(4, "14", "13", "8", "10"),
    ]
    swings = detect_swing_points(bars, lookback=1)
    assert len(swings) >= 1
    high_swings = [s for s in swings if s.is_high]
    assert any(s.price == Decimal("20") for s in high_swings)

    structure_state = analyze_structure(bars, lookback=1)
    assert structure_state.recent_swing_high == Decimal("20")


def test_regime_classification_unknown_when_insufficient_bars():
    bars = [make_test_bar(i, "100", "105", "95", "100") for i in range(5)]
    regime = classify_regime(bars, fast_period=20, slow_period=50)
    assert regime.regime == "UNKNOWN"
    assert regime.trend_direction == "NEUTRAL"
