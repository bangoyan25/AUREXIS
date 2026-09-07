"""
Comprehensive Brain Strategy tests for TASK-003 — AUREXIS-STRAT-1.0.0.
Part 1: helpers, structure tests, regime tests.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from brain.config import (
    BrainConfig,
    default_strat_config,
)
from brain.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_atr_baseline,
    calculate_ema,
    calculate_rsi,
)
from brain.market_data.types import Bar, DataSource, Tick
from brain.pipeline import SignalPipeline
from brain.regime import classify_regime
from brain.scoring import MultiFactorScorer
from brain.strategy.interfaces import SignalDirection
from brain.strategy.setups import detect_setup
from brain.structure import StructureState, analyze_structure, detect_swing_points


def make_bar(
    index: int,
    o: float,
    h: float,
    lo: float,
    c: float,
    base: datetime | None = None,
    symbol: str = "XAUUSD",
) -> Bar:
    b = base or datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    t = b + timedelta(minutes=index)
    return Bar(
        symbol=symbol, timeframe="M5",
        open_time=t, close_time=t + timedelta(minutes=5),
        open_price=Decimal(str(o)), high_price=Decimal(str(h)),
        low_price=Decimal(str(lo)), close_price=Decimal(str(c)),
        is_closed=True,
    )



def make_tick(bid: float = 2000.0, ask: float = 2000.20) -> Tick:
    t = datetime.now(UTC)
    return Tick(
        symbol="XAUUSD",
        bid=Decimal(str(bid)),
        ask=Decimal(str(ask)),
        tick_time=t, received_at=t,
        source=DataSource.MOCK,
    )


def breakout_bars() -> list[Bar]:
    return [
        make_bar(0, 2000, 2005, 1999, 2004),
        make_bar(1, 2004, 2010, 2003, 2008),   # swing high 2010
        make_bar(2, 2006, 2007, 2002, 2004),   # swing low 2002
        make_bar(3, 2004, 2012, 2003, 2009),
        make_bar(4, 2009, 2010, 2006, 2007),   # close <= 2010
        make_bar(5, 2007, 2016, 2006, 2015),   # LONG_BREAKOUT: close 2015 > 2010
    ]


def fakeout_bars() -> list[Bar]:
    return [
        make_bar(0, 2020, 2025, 2019, 2024),
        make_bar(1, 2024, 2025, 2015, 2016),   # swing low 2015
        make_bar(2, 2016, 2018, 2016, 2017),
        make_bar(3, 2017, 2020, 2015, 2019),   # swing low confirmed
        make_bar(4, 2019, 2020, 2013, 2018),   # wick through 2015, close 2018 > 2015
    ]


class TestStructureDetection:
    def test_no_swings_insufficient_bars(self) -> None:
        bars = [make_bar(i, 2000+i, 2005+i, 1999+i, 2004+i) for i in range(3)]
        assert detect_swing_points(bars, lookback=3) == []

    def test_swing_high_detected(self) -> None:
        bars = [
            make_bar(0, 2000, 2002, 1999, 2001),
            make_bar(1, 2001, 2010, 2000, 2009),
            make_bar(2, 2009, 2009, 2000, 2001),
        ]
        swings = detect_swing_points(bars, lookback=1)
        highs = [s for s in swings if s.is_high]
        assert any(s.price == Decimal("2010") for s in highs)

    def test_structure_returns_recent_levels(self) -> None:
        bars = breakout_bars()
        atr = calculate_atr(bars, 3)
        st = analyze_structure(bars, lookback=1, atr=atr)
        assert st.recent_swing_high is not None or st.recent_swing_low is not None


class TestMomentumClassification:
    def test_bullish_rsi_ascending(self) -> None:
        bars = [make_bar(i, 2000+i, 2002+i, 1999+i, 2001+i) for i in range(20)]
        rsi = calculate_rsi(bars, 14)
        assert rsi is not None and rsi > Decimal("50")

    def test_bearish_rsi_descending(self) -> None:
        bars = [make_bar(i, 2020-i, 2022-i, 2019-i, 2018-i) for i in range(20)]
        rsi = calculate_rsi(bars, 14)
        assert rsi is not None and rsi < Decimal("50")

    def test_neutral_alternating(self) -> None:
        bars = [make_bar(i, 2000, 2002, 1999, 2001.0 if i%2==0 else 2000.0) for i in range(20)]
        rsi = calculate_rsi(bars, 14)
        assert rsi is not None
        assert Decimal("40") <= rsi <= Decimal("60")


class TestVolatilityClassification:
    def test_atr_deterministic(self) -> None:
        bars = [make_bar(i, 100, 110, 90, 100) for i in range(20)]
        atr = calculate_atr(bars, 14)
        assert atr == Decimal("20")

    def test_atr_baseline_returns_decimal(self) -> None:
        bars = [make_bar(i, 100, 110, 90, 100) for i in range(70)]
        baseline = calculate_atr_baseline(bars, atr_period=14, baseline_bars=20)
        assert baseline is not None and isinstance(baseline, Decimal)


class TestADX:
    def test_adx_dict_keys(self) -> None:
        bars = [make_bar(i, 2000+i, 2002+i, 1999+i, 2001+i) for i in range(35)]
        result = calculate_adx(bars, period=14)
        assert set(result.keys()) == {"adx", "plus_di", "minus_di"}

    def test_adx_none_insufficient(self) -> None:
        bars = [make_bar(i, 2000, 2002, 1999, 2001) for i in range(10)]
        result = calculate_adx(bars, period=14)
        assert result["adx"] is None

    def test_adx_is_decimal(self) -> None:
        bars = [make_bar(i, 2000+i, 2002+i, 1999+i, 2001+i) for i in range(40)]
        result = calculate_adx(bars, period=14)
        if result["adx"] is not None:
            assert isinstance(result["adx"], Decimal)


class TestSetupDetection:
    def test_long_breakout(self) -> None:
        bars = breakout_bars()
        atr = calculate_atr(bars, 3)
        st = analyze_structure(bars, lookback=1, atr=atr)
        result = detect_setup(bars, st, atr)
        assert result.setup_type == "LONG_BREAKOUT"

    def test_insufficient_bars_returns_none(self) -> None:
        bars = [make_bar(0, 2000, 2002, 1999, 2001)]
        st = StructureState(bias="NEUTRAL", recent_swing_high=None, recent_swing_low=None,
                            last_event="NONE", structural_direction="NEUTRAL")
        result = detect_setup(bars, st, atr=Decimal("1.0"))
        assert result.setup_type == "NONE"

    def test_no_setup_continuations_or_none(self) -> None:
        bars = [make_bar(i, 2000, 2001, 1999, 2000) for i in range(5)]
        st = analyze_structure(bars, lookback=1)
        result = detect_setup(bars, st, atr=Decimal("1.0"))
        assert result.setup_type in ("NONE", "CONTINUATION")

class TestMultiFactorScoring:
    def test_news_block_returns_none(self) -> None:
        scorer = MultiFactorScorer(min_confidence_threshold=Decimal("0.50"))
        tick = make_tick()
        st = StructureState(bias="BULLISH", recent_swing_high=Decimal("2010"),
                            recent_swing_low=Decimal("2000"), last_event="BOS_BULLISH",
                            structural_direction="UP")
        from brain.regime import RegimeContext
        reg = RegimeContext(regime="TREND_UP", fast_ma=Decimal("2001"), slow_ma=Decimal("2000"),
                            trend_direction="BULLISH", adx=Decimal("25"), plus_di=Decimal("20"),
                            minus_di=Decimal("10"), trend_strength="TRENDING",
                            rsi=Decimal("60"), momentum_state="BULLISH",
                            atr=Decimal("5"), atr_baseline=None, volatility_state="NORMAL")
        sig = scorer.evaluate(tick, st, reg, news_state="PRE_EVENT")
        assert sig.direction == SignalDirection.NONE

    def test_spread_block_returns_none(self) -> None:
        scorer = MultiFactorScorer(max_spread_usd=Decimal("0.10"))
        tick = make_tick(bid=2000.0, ask=2001.0)
        from brain.regime import RegimeContext
        st = StructureState(bias="BULLISH", recent_swing_high=Decimal("2010"),
                            recent_swing_low=Decimal("2000"), last_event="BOS_BULLISH",
                            structural_direction="UP")
        reg = RegimeContext(regime="TREND_UP", fast_ma=Decimal("2001"), slow_ma=Decimal("2000"),
                            trend_direction="BULLISH", adx=Decimal("25"), plus_di=Decimal("20"),
                            minus_di=Decimal("10"), trend_strength="TRENDING",
                            rsi=Decimal("60"), momentum_state="BULLISH",
                            atr=Decimal("5"), atr_baseline=None, volatility_state="NORMAL")
        sig = scorer.evaluate(tick, st, reg, news_state="CLEAR")
        assert sig.direction == SignalDirection.NONE

    def test_regime_block_unknown(self) -> None:
        scorer = MultiFactorScorer(min_confidence_threshold=Decimal("0.50"))
        tick = make_tick()
        from brain.regime import RegimeContext
        st = StructureState(bias="BULLISH", recent_swing_high=Decimal("2010"),
                            recent_swing_low=Decimal("2000"), last_event="BOS_BULLISH",
                            structural_direction="UP")
        reg = RegimeContext(regime="UNKNOWN", fast_ma=None, slow_ma=None,
                            trend_direction="NEUTRAL", adx=None, plus_di=None,
                            minus_di=None, trend_strength="UNKNOWN",
                            rsi=None, momentum_state="NEUTRAL",
                            atr=None, atr_baseline=None, volatility_state="UNKNOWN")
        sig = scorer.evaluate(tick, st, reg, news_state="CLEAR")
        assert sig.direction == SignalDirection.NONE


class TestFailSafeInvariants:
    def test_unknown_regime_no_trade(self) -> None:
        bars = [make_bar(i, 2000+i, 2002+i, 1999+i, 2001+i) for i in range(3)]
        reg = classify_regime(bars, fast_period=50, slow_period=100)
        assert reg.regime == "UNKNOWN"
        assert not reg.permits_new_entry

    def test_news_block_overrides_confidence(self) -> None:
        scorer = MultiFactorScorer(min_confidence_threshold=Decimal("0.01"))
        tick = make_tick()
        from brain.regime import RegimeContext
        st = StructureState(bias="BULLISH", recent_swing_high=Decimal("2010"),
                            recent_swing_low=Decimal("2000"), last_event="BOS_BULLISH",
                            structural_direction="UP")
        reg = RegimeContext(regime="TREND_UP", fast_ma=Decimal("2001"), slow_ma=Decimal("2000"),
                            trend_direction="BULLISH", adx=Decimal("30"), plus_di=Decimal("25"),
                            minus_di=Decimal("10"), trend_strength="TRENDING",
                            rsi=Decimal("60"), momentum_state="BULLISH",
                            atr=Decimal("5"), atr_baseline=None, volatility_state="NORMAL")
        sig = scorer.evaluate(tick, st, reg, news_state="IN_EVENT")
        assert sig.direction == SignalDirection.NONE

    def test_unconfigured_pipeline_no_trade(self) -> None:
        pipeline = SignalPipeline()
        bars = breakout_bars()
        tick = make_tick()
        sig = pipeline.process(tick, bars)
        assert sig.direction == SignalDirection.NONE
        assert not sig.is_configured

    def test_float_not_used_in_financials(self) -> None:
        bars = breakout_bars()
        atr = calculate_atr(bars, 3)
        assert isinstance(atr, Decimal)
        rsi = calculate_rsi(bars, 3)
        assert isinstance(rsi, Decimal)
        ema = calculate_ema(bars, 3)
        assert isinstance(ema, Decimal)


class TestDefaultConfig:
    def test_default_config_is_fully_configured(self) -> None:
        cfg = default_strat_config()
        assert cfg.is_fully_configured is True

    def test_default_strategy_version(self) -> None:
        cfg = default_strat_config()
        assert cfg.strategy_version == "AUREXIS-STRAT-1.0.0"

    def test_empty_brain_config_not_configured(self) -> None:
        cfg = BrainConfig()
        assert not cfg.is_fully_configured

    def test_weights_sum_to_one(self) -> None:
        cfg = default_strat_config()
        sc = cfg.scoring
        total = (sc.weight_structure + sc.weight_trend + sc.weight_setup
                 + sc.weight_momentum + sc.weight_volatility + sc.weight_regime)
        assert total == Decimal("1.00")

