"""
Regime classification — AUREXIS Brain.
States: TREND_UP, TREND_DOWN, RANGE, TRANSITION, HIGH_VOLATILITY, UNKNOWN.
UNKNOWN / HIGH_VOLATILITY / TRANSITION → NO TRADE (fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from brain.indicators import (
    calculate_adx,
    calculate_atr,
    calculate_atr_baseline,
    calculate_ema,
    calculate_rsi,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from brain.market_data.types import Bar


NO_TRADE_REGIMES = frozenset(["UNKNOWN", "HIGH_VOLATILITY", "TRANSITION"])


@dataclass(frozen=True)
class RegimeContext:
    """Full market regime and indicator snapshot."""
    regime: str
    fast_ma: Decimal | None
    slow_ma: Decimal | None
    trend_direction: str
    adx: Decimal | None
    plus_di: Decimal | None
    minus_di: Decimal | None
    trend_strength: str
    rsi: Decimal | None
    momentum_state: str
    atr: Decimal | None
    atr_baseline: Decimal | None
    volatility_state: str

    @property
    def permits_new_entry(self) -> bool:
        return self.regime not in NO_TRADE_REGIMES

    @property
    def momentum_direction(self) -> str:
        """Backward compatibility for existing callers."""
        return self.momentum_state if self.momentum_state in ("BULLISH", "BEARISH") else "NEUTRAL"


def classify_regime(
    bars: Sequence[Bar],
    fast_period: int = 20,
    slow_period: int = 50,
    rsi_period: int = 14,
    atr_period: int = 14,
    adx_period: int = 14,
    trending_threshold: Decimal = Decimal("20"),
    rsi_bullish_min: Decimal = Decimal("52"),
    rsi_bearish_max: Decimal = Decimal("48"),
    rsi_overbought: Decimal = Decimal("70"),
    rsi_oversold: Decimal = Decimal("30"),
    atr_baseline_bars: int = 50,
    volatility_normal_ratio: Decimal = Decimal("1.50"),
    volatility_high_ratio: Decimal = Decimal("2.00"),
    max_atr_threshold: Decimal | None = None,
) -> RegimeContext:
    """Classify market regime from closed bars."""
    min_bars = max(slow_period, rsi_period + 1, atr_period + 1)
    _unknown = RegimeContext(
        regime="UNKNOWN", fast_ma=None, slow_ma=None,
        trend_direction="NEUTRAL", adx=None, plus_di=None, minus_di=None,
        trend_strength="UNKNOWN", rsi=None, momentum_state="NEUTRAL",
        atr=None, atr_baseline=None, volatility_state="UNKNOWN",
    )
    if len(bars) < min_bars:
        return _unknown

    fast_ma = calculate_ema(bars, fast_period)
    slow_ma = calculate_ema(bars, slow_period)
    rsi = calculate_rsi(bars, rsi_period)
    atr = calculate_atr(bars, atr_period)

    # ADX calculation (graceful if bars < adx_period*2 + 1)
    adx_data = calculate_adx(bars, adx_period)
    adx = adx_data["adx"]
    plus_di = adx_data["plus_di"]
    minus_di = adx_data["minus_di"]

    atr_baseline: Decimal | None = None
    if len(bars) >= atr_period + 1 + atr_baseline_bars:
        atr_baseline = calculate_atr_baseline(bars, atr_period, atr_baseline_bars)

    trend_dir = "NEUTRAL"
    if fast_ma is not None and slow_ma is not None:
        if fast_ma > slow_ma:
            trend_dir = "BULLISH"
        elif fast_ma < slow_ma:
            trend_dir = "BEARISH"

    trend_str = "UNKNOWN"
    if adx is not None:
        trend_str = "TRENDING" if adx >= trending_threshold else "WEAK"
    elif trend_dir != "NEUTRAL":
        # Fallback if insufficient bars for full ADX
        trend_str = "TRENDING"

    mom_state = "NEUTRAL"
    if rsi is not None:
        if trend_dir == "BULLISH" and rsi >= rsi_overbought or trend_dir == "BEARISH" and rsi <= rsi_oversold:
            mom_state = "EXHAUSTED"
        elif rsi >= rsi_bullish_min:
            mom_state = "BULLISH"
        elif rsi <= rsi_bearish_max:
            mom_state = "BEARISH"

    vol_state = "NORMAL"
    if atr is not None:
        if atr_baseline is not None and atr_baseline > Decimal("0"):
            ratio = atr / atr_baseline
            if ratio >= volatility_high_ratio:
                vol_state = "ABNORMAL_HIGH"
            elif ratio >= volatility_normal_ratio:
                vol_state = "EXPANDING"
            elif ratio < (Decimal("1") / volatility_normal_ratio):
                vol_state = "CONTRACTING"
        elif max_atr_threshold is not None and atr > max_atr_threshold:
            vol_state = "ABNORMAL_HIGH"

    if vol_state == "ABNORMAL_HIGH":
        regime = "HIGH_VOLATILITY"
    elif fast_ma is None or slow_ma is None:
        regime = "UNKNOWN"
    elif trend_dir == "BULLISH" and trend_str == "TRENDING" and mom_state in ("BULLISH", "NEUTRAL"):
        regime = "TREND_UP"
    elif trend_dir == "BEARISH" and trend_str == "TRENDING" and mom_state in ("BEARISH", "NEUTRAL"):
        regime = "TREND_DOWN"
    elif trend_str == "WEAK" and trend_dir != "NEUTRAL":
        regime = "TRANSITION"
    else:
        regime = "RANGE"

    return RegimeContext(
        regime=regime,
        fast_ma=fast_ma,
        slow_ma=slow_ma,
        trend_direction=trend_dir,
        adx=adx,
        plus_di=plus_di,
        minus_di=minus_di,
        trend_strength=trend_str,
        rsi=rsi,
        momentum_state=mom_state,
        atr=atr,
        atr_baseline=atr_baseline,
        volatility_state=vol_state,
    )

