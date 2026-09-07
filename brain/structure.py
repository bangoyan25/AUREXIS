"""
Market Structure Analysis on closed bars.

Detects:
- Swing Highs and Swing Lows (pivot points)
- HH, HL, LH, LL patterns
- Break of Structure (BOS) with minimum ATR displacement
- Change of Character (CHoCH)
- Equal high/low tolerance (ATR-relative)

All analysis is on confirmed closed bars. No lookahead.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from brain.market_data.types import Bar


@dataclass(frozen=True)
class SwingPoint:
    """A detected swing pivot point."""
    bar_index: int
    price: Decimal
    is_high: bool  # True = Swing High, False = Swing Low


@dataclass(frozen=True)
class StructureState:
    """Current market structure state."""
    bias: str  # "BULLISH", "BEARISH", "NEUTRAL"
    recent_swing_high: Decimal | None
    recent_swing_low: Decimal | None
    last_event: str  # "BOS_BULLISH", "BOS_BEARISH", "CHOCH_BULLISH", "CHOCH_BEARISH", "NONE"
    structural_direction: str  # "UP", "DOWN", "NEUTRAL" — computed from HH/HL sequence


def detect_swing_points(bars: Sequence[Bar], lookback: int = 3) -> list[SwingPoint]:
    """
    Detect swing pivots using strict left/right comparison.
    A swing high: bar.high > all bars within [i-lookback, i+lookback] (excluding i).
    Requires at least 2*lookback + 1 closed bars.
    lookback=3 is conservative for XAUUSD 5m/15m.
    """
    if len(bars) < (2 * lookback + 1) or lookback < 1:
        return []

    swings: list[SwingPoint] = []
    max_eval_idx = len(bars) - lookback  # need lookback bars on right

    for i in range(lookback, max_eval_idx):
        target = bars[i]

        is_swing_high = all(
            target.high_price > bars[j].high_price
            for j in range(i - lookback, i + lookback + 1)
            if j != i
        )
        if is_swing_high:
            swings.append(SwingPoint(bar_index=i, price=target.high_price, is_high=True))

        is_swing_low = all(
            target.low_price < bars[j].low_price
            for j in range(i - lookback, i + lookback + 1)
            if j != i
        )
        if is_swing_low:
            swings.append(SwingPoint(bar_index=i, price=target.low_price, is_high=False))

    return swings


def analyze_structure(
    bars: Sequence[Bar],
    lookback: int = 3,
    atr: Decimal | None = None,
    min_bos_atr_multiplier: Decimal = Decimal("0.30"),
    equal_level_tolerance_atr: Decimal = Decimal("0.10"),
) -> StructureState:
    """
    Analyze structure bias from closed bars.

    BOS requires minimum displacement = min_bos_atr_multiplier * atr (if atr provided).
    Equal-high/low tolerance = equal_level_tolerance_atr * atr.
    """
    swings = detect_swing_points(bars, lookback=lookback)
    if not swings:
        return StructureState(
            bias="NEUTRAL",
            recent_swing_high=None,
            recent_swing_low=None,
            last_event="NONE",
            structural_direction="NEUTRAL",
        )

    swing_highs = [s for s in swings if s.is_high]
    swing_lows = [s for s in swings if not s.is_high]

    recent_high = swing_highs[-1].price if swing_highs else None
    recent_low = swing_lows[-1].price if swing_lows else None

    bias = "NEUTRAL"
    last_event = "NONE"
    structural_direction = "NEUTRAL"

    min_bos: Decimal = Decimal("0")
    if atr is not None and atr > Decimal("0"):
        min_bos = atr * min_bos_atr_multiplier

    equal_tol: Decimal = Decimal("0")
    if atr is not None and atr > Decimal("0"):
        equal_tol = atr * equal_level_tolerance_atr

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        h1, h2 = swing_highs[-2].price, swing_highs[-1].price
        l1, l2 = swing_lows[-2].price, swing_lows[-1].price

        # BOS displacement check (significant move, not micro-violation)
        hh = h2 > h1 + min_bos
        hl = l2 > l1 + min_bos
        lh = h2 < h1 - min_bos
        ll = l2 < l1 - min_bos

        # Equal level: within tolerance → treat as non-directional
        eq_h = abs(h2 - h1) <= equal_tol
        eq_l = abs(l2 - l1) <= equal_tol

        if hh and hl:
            bias = "BULLISH"
            last_event = "BOS_BULLISH"
            structural_direction = "UP"
        elif lh and ll:
            bias = "BEARISH"
            last_event = "BOS_BEARISH"
            structural_direction = "DOWN"
        elif lh and hl:
            # Lower High + Higher Low = CHoCH from BEARISH → potential reversal UP
            bias = "NEUTRAL"
            last_event = "CHOCH_BULLISH"
            structural_direction = "UP"
        elif hh and ll:
            # Higher High + Lower Low = CHoCH from BULLISH → potential reversal DOWN
            bias = "NEUTRAL"
            last_event = "CHOCH_BEARISH"
            structural_direction = "DOWN"
        elif eq_h or eq_l:
            bias = "NEUTRAL"
        # else stays NEUTRAL

    elif len(swing_highs) >= 2:
        h1, h2 = swing_highs[-2].price, swing_highs[-1].price
        if h2 > h1 + min_bos:
            structural_direction = "UP"
        elif h2 < h1 - min_bos:
            structural_direction = "DOWN"

    elif len(swing_lows) >= 2:
        l1, l2 = swing_lows[-2].price, swing_lows[-1].price
        if l2 > l1 + min_bos:
            structural_direction = "UP"
        elif l2 < l1 - min_bos:
            structural_direction = "DOWN"

    return StructureState(
        bias=bias,
        recent_swing_high=recent_high,
        recent_swing_low=recent_low,
        last_event=last_event,
        structural_direction=structural_direction,
    )

