"""
Tests for Brain signal pipeline — TASK-504.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from brain.market_data.types import DataSource, Tick
from brain.pipeline import Bar, SignalPipeline
from brain.strategy.interfaces import SignalDirection


class TestSignalPipeline:
    def setup_method(self) -> None:
        self.pipeline = SignalPipeline()
        self.tick = Tick(
            symbol="XAUUSD",
            broker_symbol="XAUUSD.m",
            bid=Decimal("2735.00"),
            ask=Decimal("2735.40"),
            tick_time=datetime.now(UTC),
            received_at=datetime.now(UTC),
            source=DataSource.MOCK,
        )

    def test_pipeline_fails_closed_when_not_configured(self) -> None:
        bar = Bar(
            symbol="XAUUSD",
            timeframe="M5",
            open_time=datetime.now(UTC),
            close_time=datetime.now(UTC),
            open_price=Decimal("2730.00"),
            high_price=Decimal("2736.00"),
            low_price=Decimal("2729.00"),
            close_price=Decimal("2735.00"),
            volume=Decimal("100"),
            is_closed=True,
        )

        signal = self.pipeline.process(self.tick, [bar])
        assert signal.direction == SignalDirection.NONE
        assert not signal.is_configured
        assert signal.confidence_score is None

    def test_pipeline_rejects_unclosed_bar(self) -> None:
        unclosed_bar = Bar(
            symbol="XAUUSD",
            timeframe="M5",
            open_time=datetime.now(UTC),
            close_time=datetime.now(UTC),
            open_price=Decimal("2730.00"),
            high_price=Decimal("2736.00"),
            low_price=Decimal("2729.00"),
            close_price=Decimal("2735.00"),
            volume=Decimal("100"),
            is_closed=False,  # Still forming!
        )

        signal = self.pipeline.process(self.tick, [unclosed_bar])
        assert signal.direction == SignalDirection.NONE
        assert "INSUFFICIENT_CLOSED_BARS" in signal.market_state_summary


def test_bar_builder_tick_aggregation():
    from brain.bar_builder import BarBuilder
    builder = BarBuilder(symbol="XAUUSD", timeframe="M1")
    t0 = datetime(2026, 9, 6, 12, 0, 10, tzinfo=UTC)
    t1 = datetime(2026, 9, 6, 12, 0, 30, tzinfo=UTC)
    t2 = datetime(2026, 9, 6, 12, 1, 5, tzinfo=UTC)  # Next bucket!

    tick0 = Tick(symbol="XAUUSD", bid=Decimal("2000"), ask=Decimal("2002"), tick_time=t0, received_at=t0, source=DataSource.MOCK)
    tick1 = Tick(symbol="XAUUSD", bid=Decimal("2005"), ask=Decimal("2007"), tick_time=t1, received_at=t1, source=DataSource.MOCK)
    tick2 = Tick(symbol="XAUUSD", bid=Decimal("2002"), ask=Decimal("2004"), tick_time=t2, received_at=t2, source=DataSource.MOCK)

    assert builder.process_tick(tick0) is None
    assert builder.process_tick(tick1) is None
    closed = builder.process_tick(tick2)

    assert closed is not None
    assert closed.is_closed is True
    assert closed.open_price == Decimal("2001")  # mid of 2000, 2002
    assert closed.high_price == Decimal("2006")  # mid of 2005, 2007
    assert closed.low_price == Decimal("2001")
    assert closed.close_price == Decimal("2006")
    assert len(builder.closed_bars) == 1


def test_structure_and_regime_configured_pipeline():
    from brain.config import (
        BrainConfig,
        FreshnessConfig,
        MomentumConfig,
        RegimeConfig,
        ScoringConfig,
        SlTpConfig,
        SpreadConfig,
        StructureConfig,
        TrendConfig,
        VolatilityConfig,
    )
    cfg = BrainConfig(
        structure=StructureConfig(swing_lookback_bars=1),
        regime=RegimeConfig(adx_period=3, trending_threshold=Decimal("10")),
        trend=TrendConfig(fast_ma_period=2, slow_ma_period=4),
        momentum=MomentumConfig(rsi_period=3, rsi_overbought=Decimal("90"), rsi_oversold=Decimal("10"),
                                rsi_bullish_min=Decimal("50"), rsi_bearish_max=Decimal("45")),
        volatility=VolatilityConfig(atr_period=3),
        scoring=ScoringConfig(min_confidence_threshold=Decimal("0.50"),
                              weight_structure=Decimal("0.25"), weight_trend=Decimal("0.20"),
                              weight_setup=Decimal("0.25"), weight_momentum=Decimal("0.10"),
                              weight_volatility=Decimal("0.10"), weight_regime=Decimal("0.10")),
        sl_tp=SlTpConfig(sl_atr_buffer=Decimal("0.50"), min_sl_atr=Decimal("0.10"),
                         rr_target=Decimal("2.0"), min_rr=Decimal("1.0")),
        spread=SpreadConfig(max_spread_usd=Decimal("5.00")),
        freshness=FreshnessConfig(max_tick_staleness_ms=60000),
    )
    assert cfg.is_fully_configured is True

    # Realistic breakout pattern (zigzag + breakout bar):
    # bar 0-1: establishes swing high at 2010
    # bar 2: pullback (swing low 2002)
    # bar 3-4: higher low, test of level (close <= 2010)
    # bar 5: breakout close above swing high 2010
    pattern = [
        (2000, 2005, 1999, 2004),
        (2004, 2010, 2003, 2008),   # swing high 2010 at bar 1
        (2006, 2007, 2002, 2004),   # swing low 2002 at bar 2
        (2004, 2012, 2003, 2009),
        (2009, 2010, 2006, 2007),   # pullback (close 2007 <= 2010)
        (2007, 2016, 2006, 2015),   # LONG_BREAKOUT: close 2015 > 2010, prev close 2007 <= 2010
    ]
    base_time = datetime(2026, 9, 6, 10, 0, tzinfo=UTC)
    bars = []
    for i, (o, h, low_p, c) in enumerate(pattern):
        t = base_time + timedelta(minutes=i)
        bars.append(Bar(
            symbol="XAUUSD", timeframe="M1",
            open_time=t, close_time=t + timedelta(minutes=1),
            open_price=Decimal(str(o)), high_price=Decimal(str(h)),
            low_price=Decimal(str(low_p)), close_price=Decimal(str(c)),
            is_closed=True,
        ))

    pipeline = SignalPipeline(config=cfg)
    t_now = datetime.now(UTC)
    tick = Tick(
        symbol="XAUUSD",
        bid=Decimal("2015.00"),
        ask=Decimal("2015.20"),
        tick_time=t_now,
        received_at=t_now,
        source=DataSource.MOCK,
    )

    signal = pipeline.process(tick, bars)
    assert signal.is_configured is True
    assert signal.direction == SignalDirection.BUY
    assert signal.confidence_score is not None
    assert signal.confidence_score >= Decimal("0.50")
    assert signal.suggested_stop_loss is not None
    # Strategy version must be traceable
    assert signal.strategy_version == "AUREXIS-STRAT-1.0.0"




