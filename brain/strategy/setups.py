"""
Breakout and Fakeout setup detection — AUREXIS Brain.

Operates strictly on confirmed closed bars.
Setup types:
- LONG_BREAKOUT: Closed above prior swing high by >= min_displacement_atr * atr.
- SHORT_BREAKOUT: Closed below prior swing low by >= min_displacement_atr * atr.
- LONG_FAKEOUT_REVERSAL: Penetrated below prior swing low, closed back above it.
- SHORT_FAKEOUT_REVERSAL: Penetrated above prior swing high, closed back below it.
- CONTINUATION: In-trend structural continuation (default when aligned).
- NONE: No setup detected.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from brain.market_data.types import Bar
    from brain.structure import StructureState


@dataclass(frozen=True)
class SetupDetectionResult:
    setup_type: str  # "LONG_BREAKOUT", "SHORT_BREAKOUT", "LONG_FAKEOUT_REVERSAL", "SHORT_FAKEOUT_REVERSAL", "CONTINUATION", "NONE"
    reference_price: Decimal | None
    displacement_atr: Decimal | None
    is_reversal: bool
    summary: str


def detect_setup(
    bars: Sequence[Bar],
    structure: StructureState,
    atr: Decimal | None = None,
    min_displacement_atr: Decimal = Decimal("0.30"),
) -> SetupDetectionResult:
    """
    Detect breakout or fakeout setup from latest closed bars.
    Requires at least 2 closed bars.
    """
    if len(bars) < 2:
        return SetupDetectionResult(
            setup_type="NONE",
            reference_price=None,
            displacement_atr=None,
            is_reversal=False,
            summary="Insufficient closed bars",
        )

    last_bar = bars[-1]
    prev_bar = bars[-2]
    disp_req = (atr * min_displacement_atr) if (atr and atr > Decimal("0")) else Decimal("0")

    sh = structure.recent_swing_high
    sl = structure.recent_swing_low

    # 1. Breakout UP: last bar closed convincingly above swing high
    if sh is not None and last_bar.close_price > sh + disp_req and prev_bar.close_price <= sh:
        disp = (last_bar.close_price - sh) / atr if (atr and atr > Decimal("0")) else Decimal("1.0")
        return SetupDetectionResult(
            setup_type="LONG_BREAKOUT",
            reference_price=sh,
            displacement_atr=disp,
            is_reversal=False,
            summary=f"LONG_BREAKOUT above {sh} with disp {disp:.2f} ATR",
        )

    # 2. Breakout DOWN: last bar closed convincingly below swing low
    if sl is not None and last_bar.close_price < sl - disp_req and prev_bar.close_price >= sl:
        disp = (sl - last_bar.close_price) / atr if (atr and atr > Decimal("0")) else Decimal("1.0")
        return SetupDetectionResult(
            setup_type="SHORT_BREAKOUT",
            reference_price=sl,
            displacement_atr=disp,
            is_reversal=False,
            summary=f"SHORT_BREAKOUT below {sl} with disp {disp:.2f} ATR",
        )

    # 3. Fakeout UP (Bearish reversal): penetrated above swing high, but closed back below it
    if sh is not None and last_bar.high_price > sh and last_bar.close_price < sh:
        return SetupDetectionResult(
            setup_type="SHORT_FAKEOUT_REVERSAL",
            reference_price=sh,
            displacement_atr=Decimal("0.0"),
            is_reversal=True,
            summary=f"SHORT_FAKEOUT rejected at {sh}",
        )

    # 4. Fakeout DOWN (Bullish reversal): penetrated below swing low, but closed back above it
    if sl is not None and last_bar.low_price < sl and last_bar.close_price > sl:
        return SetupDetectionResult(
            setup_type="LONG_FAKEOUT_REVERSAL",
            reference_price=sl,
            displacement_atr=Decimal("0.0"),
            is_reversal=True,
            summary=f"LONG_FAKEOUT rejected at {sl}",
        )

    # 5. Continuation fallback if structure has bias
    if structure.bias in ("BULLISH", "BEARISH"):
        return SetupDetectionResult(
            setup_type="CONTINUATION",
            reference_price=sh if structure.bias == "BULLISH" else sl,
            displacement_atr=Decimal("0.0"),
            is_reversal=False,
            summary="Trend continuation",
        )

    return SetupDetectionResult(
        setup_type="NONE",
        reference_price=None,
        displacement_atr=None,
        is_reversal=False,
        summary="No active setup",
    )
