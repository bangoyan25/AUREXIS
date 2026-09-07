"""
Brain configuration — AUREXIS-STRAT-1.0.0.
Single canonical configuration object. Fail-closed: is_fully_configured=False when any required field is None.
All initial defaults documented in docs/STRATEGY_PARAMETERS.md.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class StructureConfig(BaseModel):
    swing_lookback_bars: int | None = Field(default=None)
    min_bos_atr_multiplier: Decimal | None = Field(default=None)
    equal_level_tolerance_atr: Decimal | None = Field(default=None)
    max_level_age_bars: int | None = Field(default=None)


class RegimeConfig(BaseModel):
    adx_period: int | None = Field(default=None)
    trending_threshold: Decimal | None = Field(default=None)
    regime_confirmation_bars: int | None = Field(default=None)
    volatility_baseline_bars: int | None = Field(default=None)
    volatility_normal_ratio: Decimal | None = Field(default=None)
    volatility_high_ratio: Decimal | None = Field(default=None)


class TrendConfig(BaseModel):
    fast_ma_period: int | None = Field(default=None)
    slow_ma_period: int | None = Field(default=None)
    trend_consistency_bars: int | None = Field(default=None)


class MomentumConfig(BaseModel):
    rsi_period: int | None = Field(default=None)
    rsi_overbought: Decimal | None = Field(default=None)
    rsi_oversold: Decimal | None = Field(default=None)
    rsi_bullish_min: Decimal | None = Field(default=None)
    rsi_bearish_max: Decimal | None = Field(default=None)


class VolatilityConfig(BaseModel):
    atr_period: int | None = Field(default=None)
    atr_baseline_bars: int | None = Field(default=None)
    normal_ratio_upper: Decimal | None = Field(default=None)
    abnormal_high_ratio: Decimal | None = Field(default=None)
    max_atr_threshold_usd: Decimal | None = Field(default=None)


class BreakoutConfig(BaseModel):
    breakout_confirmation_bars: int | None = Field(default=None)
    min_displacement_atr: Decimal | None = Field(default=None)
    setup_expiry_bars: int | None = Field(default=None)
    fakeout_reversal_bars: int | None = Field(default=None)


class ScoringConfig(BaseModel):
    min_confidence_threshold: Decimal | None = Field(default=None)
    weight_structure: Decimal | None = Field(default=None)
    weight_trend: Decimal | None = Field(default=None)
    weight_setup: Decimal | None = Field(default=None)
    weight_momentum: Decimal | None = Field(default=None)
    weight_volatility: Decimal | None = Field(default=None)
    weight_regime: Decimal | None = Field(default=None)


class SlTpConfig(BaseModel):
    sl_atr_buffer: Decimal | None = Field(default=None)
    min_sl_atr: Decimal | None = Field(default=None)
    rr_target: Decimal | None = Field(default=None)
    min_rr: Decimal | None = Field(default=None)


class SpreadConfig(BaseModel):
    max_spread_usd: Decimal | None = Field(default=None)


class FreshnessConfig(BaseModel):
    max_tick_staleness_ms: int | None = Field(default=None)


class DailyRiskConfig(BaseModel):
    daily_loss_limit_pct: Decimal | None = Field(default=None)
    max_drawdown_pct: Decimal | None = Field(default=None)
    caution_drawdown_pct: Decimal | None = Field(default=None)
    risk_per_trade_pct: Decimal | None = Field(default=None)
    profit_lock_activation_usd: Decimal | None = Field(default=None)
    profit_lock_ratio: Decimal | None = Field(default=None)


class BrainConfig(BaseModel):
    """Complete Brain strategy configuration — AUREXIS-STRAT-1.0.0."""
    strategy_id: str = "AUREXIS_CORE"
    strategy_version: str = "AUREXIS-STRAT-1.0.0"
    structure: StructureConfig = Field(default_factory=StructureConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    trend: TrendConfig = Field(default_factory=TrendConfig)
    momentum: MomentumConfig = Field(default_factory=MomentumConfig)
    volatility: VolatilityConfig = Field(default_factory=VolatilityConfig)
    breakout: BreakoutConfig = Field(default_factory=BreakoutConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    sl_tp: SlTpConfig = Field(default_factory=SlTpConfig)
    spread: SpreadConfig = Field(default_factory=SpreadConfig)
    freshness: FreshnessConfig = Field(default_factory=FreshnessConfig)
    daily_risk: DailyRiskConfig = Field(default_factory=DailyRiskConfig)

    @property
    def is_fully_configured(self) -> bool:
        """Fail-closed: all required parameters must be set."""
        return (
            self.structure.swing_lookback_bars is not None
            and self.regime.adx_period is not None
            and self.regime.trending_threshold is not None
            and self.trend.fast_ma_period is not None
            and self.trend.slow_ma_period is not None
            and self.momentum.rsi_period is not None
            and self.volatility.atr_period is not None
            and self.scoring.min_confidence_threshold is not None
        )


def default_strat_config() -> BrainConfig:
    """
    Initial strategy defaults for AUREXIS-STRAT-1.0.0.
    These are starting values — NOT optimized. Validate via backtesting.
    See docs/STRATEGY_PARAMETERS.md for rationale.
    """
    return BrainConfig(
        strategy_id="AUREXIS_CORE",
        strategy_version="AUREXIS-STRAT-1.0.0",
        structure=StructureConfig(
            swing_lookback_bars=3,
            min_bos_atr_multiplier=Decimal("0.30"),
            equal_level_tolerance_atr=Decimal("0.10"),
            max_level_age_bars=100,
        ),
        regime=RegimeConfig(
            adx_period=14,
            trending_threshold=Decimal("20"),
            regime_confirmation_bars=2,
            volatility_baseline_bars=50,
            volatility_normal_ratio=Decimal("1.50"),
            volatility_high_ratio=Decimal("2.00"),
        ),
        trend=TrendConfig(
            fast_ma_period=20,
            slow_ma_period=50,
            trend_consistency_bars=3,
        ),
        momentum=MomentumConfig(
            rsi_period=14,
            rsi_overbought=Decimal("70"),
            rsi_oversold=Decimal("30"),
            rsi_bullish_min=Decimal("52"),
            rsi_bearish_max=Decimal("48"),
        ),
        volatility=VolatilityConfig(
            atr_period=14,
            atr_baseline_bars=50,
            normal_ratio_upper=Decimal("1.50"),
            abnormal_high_ratio=Decimal("2.00"),
            max_atr_threshold_usd=Decimal("15.00"),
        ),
        breakout=BreakoutConfig(
            breakout_confirmation_bars=1,
            min_displacement_atr=Decimal("0.30"),
            setup_expiry_bars=3,
            fakeout_reversal_bars=1,
        ),
        scoring=ScoringConfig(
            min_confidence_threshold=Decimal("0.70"),
            weight_structure=Decimal("0.25"),
            weight_trend=Decimal("0.20"),
            weight_setup=Decimal("0.25"),
            weight_momentum=Decimal("0.10"),
            weight_volatility=Decimal("0.10"),
            weight_regime=Decimal("0.10"),
        ),
        sl_tp=SlTpConfig(
            sl_atr_buffer=Decimal("0.50"),
            min_sl_atr=Decimal("0.30"),
            rr_target=Decimal("2.0"),
            min_rr=Decimal("1.5"),
        ),
        spread=SpreadConfig(max_spread_usd=Decimal("1.00")),
        freshness=FreshnessConfig(max_tick_staleness_ms=2000),
        daily_risk=DailyRiskConfig(
            daily_loss_limit_pct=Decimal("2.0"),
            max_drawdown_pct=Decimal("5.0"),
            caution_drawdown_pct=Decimal("70"),
            risk_per_trade_pct=Decimal("0.50"),
            profit_lock_activation_usd=Decimal("10.00"),
            profit_lock_ratio=Decimal("0.70"),
        ),
    )

