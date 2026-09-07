"""
Multi-factor evidence assembly and confidence scoring — AUREXIS-STRAT-1.0.0.
6 independent dimensions: Structure(25%), Trend(20%), Setup(25%),
Momentum(10%), Volatility(10%), Regime(10%).
Hard gates: regime UNKNOWN/HIGH_VOLATILITY/TRANSITION, news, spread.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from brain.strategy.interfaces import CandidateSignal, SignalDirection

if TYPE_CHECKING:
    from brain.market_data.types import Tick
    from brain.regime import RegimeContext
    from brain.structure import StructureState


def _score_structure(direction: str, struct: StructureState) -> Decimal:
    if direction == "BUY":
        if struct.bias == "BULLISH":
            return Decimal("1.0")
        if struct.last_event == "CHOCH_BULLISH":
            return Decimal("0.6")
        if struct.structural_direction == "UP":
            return Decimal("0.4")
    else:
        if struct.bias == "BEARISH":
            return Decimal("1.0")
        if struct.last_event == "CHOCH_BEARISH":
            return Decimal("0.6")
        if struct.structural_direction == "DOWN":
            return Decimal("0.4")
    return Decimal("0.0")


def _score_trend(direction: str, reg: RegimeContext) -> Decimal:
    score = Decimal("0.0")
    aligned = (direction == "BUY" and reg.trend_direction == "BULLISH") or (direction == "SELL" and reg.trend_direction == "BEARISH")
    if aligned:
        score += Decimal("0.5")
    if reg.trend_strength == "TRENDING":
        score += Decimal("0.5")
    return score


def _score_setup(direction: str, setup: str) -> Decimal:
    if (direction == "BUY" and setup == "LONG_BREAKOUT") or (direction == "SELL" and setup == "SHORT_BREAKOUT"):
        return Decimal("1.0")
    if (direction == "BUY" and setup == "LONG_FAKEOUT_REVERSAL") or (direction == "SELL" and setup == "SHORT_FAKEOUT_REVERSAL"):
        return Decimal("0.8")
    if setup == "CONTINUATION":
        return Decimal("0.5")
    return Decimal("0.0")


def _score_momentum(direction: str, reg: RegimeContext) -> Decimal:
    ms = reg.momentum_state
    if ms == "EXHAUSTED":
        return Decimal("0.0")
    if (direction == "BUY" and ms == "BULLISH") or (direction == "SELL" and ms == "BEARISH"):
        return Decimal("1.0")
    if ms == "NEUTRAL":
        return Decimal("0.5")
    return Decimal("0.0")


def _score_volatility(reg: RegimeContext) -> Decimal:
    vs = reg.volatility_state
    if vs == "NORMAL":
        return Decimal("1.0")
    if vs == "CONTRACTING":
        return Decimal("0.8")
    if vs == "EXPANDING":
        return Decimal("0.5")
    return Decimal("0.0")


def _score_regime(direction: str, reg: RegimeContext) -> Decimal:
    r = reg.regime
    if (direction == "BUY" and r == "TREND_UP") or (direction == "SELL" and r == "TREND_DOWN"):
        return Decimal("1.0")
    if r == "RANGE":
        return Decimal("0.3")
    return Decimal("0.0")


class MultiFactorScorer:
    """Weighted 6-dimension evidence scorer for AUREXIS-STRAT-1.0.0."""

    def __init__(
        self,
        strategy_id: str = "AUREXIS_CORE",
        strategy_version: str = "AUREXIS-STRAT-1.0.0",
        min_confidence_threshold: Decimal = Decimal("0.70"),
        weight_structure: Decimal = Decimal("0.25"),
        weight_trend: Decimal = Decimal("0.20"),
        weight_setup: Decimal = Decimal("0.25"),
        weight_momentum: Decimal = Decimal("0.10"),
        weight_volatility: Decimal = Decimal("0.10"),
        weight_regime: Decimal = Decimal("0.10"),
        sl_atr_buffer: Decimal = Decimal("0.50"),
        min_sl_atr: Decimal = Decimal("0.30"),
        rr_target: Decimal = Decimal("2.0"),
        min_rr: Decimal = Decimal("1.5"),
        max_spread_usd: Decimal = Decimal("1.00"),
    ) -> None:
        self.strategy_id = strategy_id
        self.strategy_version = strategy_version
        self.min_conf = min_confidence_threshold
        self.w_st = weight_structure
        self.w_tr = weight_trend
        self.w_se = weight_setup
        self.w_mo = weight_momentum
        self.w_vo = weight_volatility
        self.w_re = weight_regime
        self.sl_buffer = sl_atr_buffer
        self.min_sl_atr = min_sl_atr
        self.rr = rr_target
        self.min_rr = min_rr
        self.max_spread = max_spread_usd

    def evaluate(
        self,
        tick: Tick,
        structure: StructureState,
        regime_ctx: RegimeContext,
        news_state: str = "CLEAR",
        setup_type: str = "CONTINUATION",
    ) -> CandidateSignal:
        """Synthesize all evidence dimensions into a scored CandidateSignal."""

        def _none(summary: str) -> CandidateSignal:
            return CandidateSignal(
                symbol=tick.symbol,
                direction=SignalDirection.NONE,
                confidence_score=Decimal("0.0"),
                suggested_stop_loss=None,
                suggested_take_profit=None,
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                market_state_summary=summary,
                is_configured=True,
            )

        if news_state != "CLEAR":
            return _none(f"Blocked by news: {news_state}")
        if tick.spread > self.max_spread:
            return _none(f"Blocked by spread: {tick.spread} > {self.max_spread}")
        if not regime_ctx.permits_new_entry:
            return _none(f"Blocked by regime: {regime_ctx.regime}")

        best_signal = _none("No directional confluence")
        best_conf = Decimal("0.0")

        for d in ("BUY", "SELL"):
            s_st = _score_structure(d, structure)
            s_tr = _score_trend(d, regime_ctx)
            s_se = _score_setup(d, setup_type)
            s_mo = _score_momentum(d, regime_ctx)
            s_vo = _score_volatility(regime_ctx)
            s_re = _score_regime(d, regime_ctx)

            conf = (s_st * self.w_st + s_tr * self.w_tr + s_se * self.w_se
                    + s_mo * self.w_mo + s_vo * self.w_vo + s_re * self.w_re)
            if conf < self.min_conf or conf <= best_conf:
                continue

            atr = regime_ctx.atr or Decimal("1.0")
            sl, tp = self._compute_sl_tp(tick, structure, atr, d)
            if sl is None:
                continue

            best_conf = conf
            best_signal = CandidateSignal(
                symbol=tick.symbol,
                direction=SignalDirection.BUY if d == "BUY" else SignalDirection.SELL,
                confidence_score=conf,
                suggested_stop_loss=sl,
                suggested_take_profit=tp,
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                market_state_summary=f"{d} conf={conf:.3f} st={s_st} tr={s_tr} se={s_se}",
                is_configured=True,
                entry_reference=tick.ask if d == "BUY" else tick.bid,
            )

        return best_signal

    def _compute_sl_tp(
        self,
        tick: Tick,
        structure: StructureState,
        atr: Decimal,
        direction: str,
    ) -> tuple[Decimal | None, Decimal | None]:
        min_dist = atr * self.min_sl_atr
        if direction == "BUY":
            entry = tick.ask
            ref = structure.recent_swing_low
            sl_base = (ref if ref is not None and ref < entry else entry - atr)
            sl = sl_base - (atr * self.sl_buffer)
            risk = entry - sl
            if risk < min_dist:
                return None, None
            tp = entry + (risk * self.rr)
        else:
            entry = tick.bid
            ref = structure.recent_swing_high
            sl_base = (ref if ref is not None and ref > entry else entry + atr)
            sl = sl_base + (atr * self.sl_buffer)
            risk = sl - entry
            if risk < min_dist:
                return None, None
            tp = entry - (risk * self.rr)
        return sl, tp

