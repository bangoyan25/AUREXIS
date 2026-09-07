"""
Closed-bar technical indicators for AUREXIS Brain.

Strictly operates on closed Bar lists.
Decimal calculations only.
No lookahead, no future data, deterministic.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from brain.market_data.types import Bar


def calculate_sma(bars: Sequence[Bar], period: int) -> Decimal | None:
    """Calculate Simple Moving Average of close prices over period."""
    if len(bars) < period or period <= 0:
        return None
    selected = bars[-period:]
    total = sum((b.close_price for b in selected), Decimal("0"))
    return total / Decimal(str(period))


def calculate_ema(bars: Sequence[Bar], period: int) -> Decimal | None:
    """Calculate Exponential Moving Average of close prices."""
    if len(bars) < period or period <= 0:
        return None
    # Initialize with SMA of first 'period' bars
    k = Decimal("2") / Decimal(str(period + 1))
    current_ema = sum((b.close_price for b in bars[:period]), Decimal("0")) / Decimal(str(period))
    for b in bars[period:]:
        current_ema = (b.close_price * k) + (current_ema * (Decimal("1") - k))
    return current_ema


def calculate_atr(bars: Sequence[Bar], period: int) -> Decimal | None:
    """
    Calculate Average True Range (ATR) over period closed bars.
    True Range = max(H - L, abs(H - previous_C), abs(L - previous_C))
    """
    if len(bars) < period + 1 or period <= 0:
        return None

    true_ranges: list[Decimal] = []
    for i in range(1, len(bars)):
        current = bars[i]
        prev = bars[i - 1]
        tr = max(
            current.high_price - current.low_price,
            abs(current.high_price - prev.close_price),
            abs(current.low_price - prev.close_price),
        )
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    # Wilder's Smoothing for ATR
    atr = sum(true_ranges[:period], Decimal("0")) / Decimal(str(period))
    for tr in true_ranges[period:]:
        atr = (atr * Decimal(str(period - 1)) + tr) / Decimal(str(period))
    return atr


def calculate_rsi(bars: Sequence[Bar], period: int) -> Decimal | None:
    """
    Calculate Relative Strength Index (RSI) over period closed bars.
    """
    if len(bars) < period + 1 or period <= 0:
        return None

    gains: list[Decimal] = []
    losses: list[Decimal] = []

    for i in range(1, len(bars)):
        change = bars[i].close_price - bars[i - 1].close_price
        if change > Decimal("0"):
            gains.append(change)
            losses.append(Decimal("0"))
        else:
            gains.append(Decimal("0"))
            losses.append(abs(change))

    if len(gains) < period:
        return None

    avg_gain = sum(gains[:period], Decimal("0")) / Decimal(str(period))
    avg_loss = sum(losses[:period], Decimal("0")) / Decimal(str(period))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * Decimal(str(period - 1)) + gains[i]) / Decimal(str(period))
        avg_loss = (avg_loss * Decimal(str(period - 1)) + losses[i]) / Decimal(str(period))

    if avg_loss == Decimal("0"):
        return Decimal("100")
    if avg_gain == Decimal("0"):
        return Decimal("0")

    rs = avg_gain / avg_loss
    rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
    return rsi


def calculate_atr_baseline(bars: Sequence[Bar], atr_period: int, baseline_bars: int) -> Decimal | None:
    """
    Rolling ATR baseline for normalization.
    Computes individual ATR values over a sliding baseline window.
    Returns their simple average as the baseline reference.
    Minimum bars required: atr_period + 1 + baseline_bars.
    """
    required = atr_period + 1 + baseline_bars
    if len(bars) < required or baseline_bars <= 0:
        return None

    total_bars = len(bars)
    atr_values: list[Decimal] = []
    for offset in range(baseline_bars):
        end_idx = total_bars - baseline_bars + offset + 1
        window = bars[:end_idx]
        val = calculate_atr(window, atr_period)
        if val is not None:
            atr_values.append(val)

    if not atr_values:
        return None
    return sum(atr_values, Decimal("0")) / Decimal(str(len(atr_values)))


def _compute_dx(plus_di: Decimal, minus_di: Decimal) -> Decimal:
    total = plus_di + minus_di
    if total == Decimal("0"):
        return Decimal("0")
    return (abs(plus_di - minus_di) / total) * Decimal("100")


def calculate_adx(bars: Sequence[Bar], period: int) -> dict[str, Decimal | None]:
    """
    Calculate ADX, +DI, -DI using Wilder smoothing on closed bars.

    Returns dict with keys: "adx", "plus_di", "minus_di".
    ADX is 0-100 strength indicator (no direction).
    +DI > -DI → bullish directional bias.
    Requires at least 2*period + 1 bars.
    """
    result: dict[str, Decimal | None] = {"adx": None, "plus_di": None, "minus_di": None}
    if len(bars) < period * 2 + 1 or period <= 0:
        return result

    pdm_list: list[Decimal] = []
    ndm_list: list[Decimal] = []
    tr_list: list[Decimal] = []

    for i in range(1, len(bars)):
        h = bars[i].high_price
        lo = bars[i].low_price
        pc = bars[i - 1].close_price
        ph = bars[i - 1].high_price
        pl = bars[i - 1].low_price

        tr = max(h - lo, abs(h - pc), abs(lo - pc))
        tr_list.append(tr)

        up_move = h - ph
        down_move = pl - lo

        pdm_list.append(up_move if up_move > down_move and up_move > Decimal("0") else Decimal("0"))
        ndm_list.append(down_move if down_move > up_move and down_move > Decimal("0") else Decimal("0"))


    if len(tr_list) < period:
        return result

    p = Decimal(str(period))
    atr_s = sum(tr_list[:period], Decimal("0"))
    pdm_s = sum(pdm_list[:period], Decimal("0"))
    ndm_s = sum(ndm_list[:period], Decimal("0"))

    def _di(dm_s: Decimal, atr_smooth: Decimal) -> Decimal:
        if atr_smooth == Decimal("0"):
            return Decimal("0")
        return (dm_s / atr_smooth) * Decimal("100")

    dx_list: list[Decimal] = [_compute_dx(_di(pdm_s, atr_s), _di(ndm_s, atr_s))]

    for i in range(period, len(tr_list)):
        atr_s = atr_s - (atr_s / p) + tr_list[i]
        pdm_s = pdm_s - (pdm_s / p) + pdm_list[i]
        ndm_s = ndm_s - (ndm_s / p) + ndm_list[i]
        dx_list.append(_compute_dx(_di(pdm_s, atr_s), _di(ndm_s, atr_s)))

    if len(dx_list) < period:
        return result

    adx_val = sum(dx_list[:period], Decimal("0")) / p
    for dx in dx_list[period:]:
        adx_val = (adx_val * (p - Decimal("1")) + dx) / p

    result["adx"] = adx_val
    result["plus_di"] = _di(pdm_s, atr_s)
    result["minus_di"] = _di(ndm_s, atr_s)
    return result

