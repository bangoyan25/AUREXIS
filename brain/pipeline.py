"""
AUREXIS Brain Signal Pipeline  TASK-504.

Implements the multi-stage pipeline specified in docs/BRAIN_SPECIFICATION.md:
  1. Market State Normalization
  2. Market Structure Analysis (Closed bars only)
  3. Regime Classification
  4. Trend & Momentum Context
  5. Volatility Context
  6. Setup Evaluation (Continuation, Breakout, Fakeout)
  7. Multi-factor Evidence Assembly & Confidence Scoring
  8. CandidateSignal Emission

CRITICAL ARCHITECTURAL RULES:
- The Brain PROPOSES candidate signals. It NEVER executes trades directly.
- CLOSED BARS are authoritative for structural/indicator analysis.
- Ticks are used exclusively for live price, spread, and staleness validation.
- Missing configuration or empirical parameters -> NOT_CONFIGURED (no trade proposal).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from backend.core.logging import get_logger
from brain.config import BrainConfig
from brain.market_data.types import Bar, Tick
from brain.regime import classify_regime
from brain.scoring import MultiFactorScorer
from brain.strategy.interfaces import (
    CandidateSignal,
    SignalDirection,
)
from brain.strategy.setups import detect_setup
from brain.structure import analyze_structure

__all__ = ["Bar", "BrainConfig", "CandidateSignal", "SignalPipeline"]

logger = get_logger("brain.pipeline")




@dataclass(frozen=True)
class PipelineEvidence:
    """Structured evidence assemble across all 6 dimensions."""
    structure_bias: str  # "BULLISH", "BEARISH", "NEUTRAL"
    regime: str          # "TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY", "UNKNOWN"
    trend_aligned: bool
    momentum_aligned: bool
    volatility_normal: bool
    setup_type: str      # "TREND_CONTINUATION", "BREAKOUT", "BULLISH_FAKEOUT", "BEARISH_FAKEOUT", "NONE"
    evidence_score: Decimal
    raw_details: dict[str, Any] = field(default_factory=dict)


class SignalPipeline:
    """
    Modular execution pipeline for generating CandidateSignals.

    Orchestrates the analytical stages deterministically.
    If any stage detects invalid data or missing configuration,
    the pipeline safely emits a NONE direction CandidateSignal.
    """

    def __init__(
        self,
        strategy_id: str = "AUREXIS_CORE",
        strategy_version: str = "AUREXIS-STRAT-1.0.0",
        config: BrainConfig | None = None,
    ) -> None:
        self.config = config or BrainConfig(strategy_id=strategy_id, strategy_version=strategy_version)
        self.strategy_id = self.config.strategy_id
        self.strategy_version = self.config.strategy_version


    @property
    def is_configured(self) -> bool:
        return self.config.is_fully_configured

    def process(
        self,
        latest_tick: Tick,
        closed_bars: list[Bar],
        news_state: str = "CLEAR",
        correlation_id: str | None = None,
    ) -> CandidateSignal:
        """
        Run the complete pipeline against current tick and historical closed bars.

        Returns a CandidateSignal for the Risk Engine to evaluate.
        """
        cid = correlation_id or str(uuid.uuid4())

        # Stage 1: Closed-bar rule verification
        if not closed_bars or not all(b.is_closed for b in closed_bars):
            logger.warning("brain.pipeline.insufficient_closed_bars", correlation_id=cid)
            return self._empty_signal(latest_tick.symbol, "INSUFFICIENT_CLOSED_BARS")

        # Stage 2: Configuration check (Fail-closed)
        if not self.is_configured:
            logger.debug("brain.pipeline.strategy_not_configured", correlation_id=cid)
            return CandidateSignal(
                symbol=latest_tick.symbol,
                direction=SignalDirection.NONE,
                confidence_score=None,
                suggested_stop_loss=None,
                suggested_take_profit=None,
                strategy_id=self.strategy_id,
                strategy_version=self.strategy_version,
                market_state_summary="Strategy parameters UNDEFINED; pipeline operating in fail-safe mode.",
                is_configured=False,
            )

        # Stage 3: Tick freshness check
        max_stale_ms = self.config.freshness.max_tick_staleness_ms
        if max_stale_ms is not None:
            staleness_ms = latest_tick.staleness_seconds() * 1000
            if staleness_ms > max_stale_ms:
                return self._empty_signal(latest_tick.symbol, "STALE_TICK")

        # Stage 4: Market structure analysis on closed bars
        lookback = self.config.structure.swing_lookback_bars or 3
        atr_period = self.config.volatility.atr_period or 14
        from brain.indicators import calculate_atr
        raw_atr = calculate_atr(closed_bars, atr_period)
        min_bos = self.config.structure.min_bos_atr_multiplier or Decimal("0.30")
        eq_tol = self.config.structure.equal_level_tolerance_atr or Decimal("0.10")
        structure_state = analyze_structure(
            closed_bars,
            lookback=lookback,
            atr=raw_atr,
            min_bos_atr_multiplier=min_bos,
            equal_level_tolerance_atr=eq_tol,
        )

        # Stage 5: Regime & indicator context analysis
        regime_ctx = classify_regime(
            bars=closed_bars,
            fast_period=self.config.trend.fast_ma_period or 20,
            slow_period=self.config.trend.slow_ma_period or 50,
            rsi_period=self.config.momentum.rsi_period or 14,
            atr_period=atr_period,
            adx_period=self.config.regime.adx_period or 14,
            trending_threshold=self.config.regime.trending_threshold or Decimal("20"),
            rsi_bullish_min=self.config.momentum.rsi_bullish_min or Decimal("52"),
            rsi_bearish_max=self.config.momentum.rsi_bearish_max or Decimal("48"),
            rsi_overbought=self.config.momentum.rsi_overbought or Decimal("70"),
            rsi_oversold=self.config.momentum.rsi_oversold or Decimal("30"),
            atr_baseline_bars=self.config.volatility.atr_baseline_bars or 50,
            volatility_normal_ratio=self.config.volatility.normal_ratio_upper or Decimal("1.50"),
            volatility_high_ratio=self.config.volatility.abnormal_high_ratio or Decimal("2.00"),
            max_atr_threshold=self.config.volatility.max_atr_threshold_usd,
        )

        # Stage 6: Setup detection (breakout / fakeout / continuation)
        setup_res = detect_setup(
            bars=closed_bars,
            structure=structure_state,
            atr=raw_atr,
            min_displacement_atr=self.config.breakout.min_displacement_atr or Decimal("0.30"),
        )

        # Stage 7: Multi-factor scoring with all configured weights
        min_conf = self.config.scoring.min_confidence_threshold or Decimal("0.70")
        sl_cfg = self.config.sl_tp
        spread_cfg = self.config.spread
        scorer = MultiFactorScorer(
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            min_confidence_threshold=min_conf,
            weight_structure=self.config.scoring.weight_structure or Decimal("0.25"),
            weight_trend=self.config.scoring.weight_trend or Decimal("0.20"),
            weight_setup=self.config.scoring.weight_setup or Decimal("0.25"),
            weight_momentum=self.config.scoring.weight_momentum or Decimal("0.10"),
            weight_volatility=self.config.scoring.weight_volatility or Decimal("0.10"),
            weight_regime=self.config.scoring.weight_regime or Decimal("0.10"),
            sl_atr_buffer=sl_cfg.sl_atr_buffer or Decimal("0.50"),
            min_sl_atr=sl_cfg.min_sl_atr or Decimal("0.30"),
            rr_target=sl_cfg.rr_target or Decimal("2.0"),
            min_rr=sl_cfg.min_rr or Decimal("1.5"),
            max_spread_usd=spread_cfg.max_spread_usd or Decimal("1.00"),
        )

        signal = scorer.evaluate(
            tick=latest_tick,
            structure=structure_state,
            regime_ctx=regime_ctx,
            news_state=news_state,
            setup_type=setup_res.setup_type,
        )

        # Attach setup_type and correlation_id to CandidateSignal
        if signal.direction != SignalDirection.NONE:
            from dataclasses import replace
            signal = replace(signal, correlation_id=cid, setup_type=setup_res.setup_type)

        return signal



    def _empty_signal(self, symbol: str, reason: str) -> CandidateSignal:
        return CandidateSignal(
            symbol=symbol,
            direction=SignalDirection.NONE,
            confidence_score=None,
            suggested_stop_loss=None,
            suggested_take_profit=None,
            strategy_id=self.strategy_id,
            strategy_version=self.strategy_version,
            market_state_summary=reason,
            is_configured=self.is_configured,
        )
