"""
Risk Engine configuration.

Locked decisions (owner-approved 2026-09-06):
  daily_reset_timezone   = UTC
  drawdown_reference     = lifetime HWM
  position_sizing        = percentage-of-equity risk
  profit_lock_formula    = PCT_RETRACE
  profit_lock_threshold  = $10 USD
  profit_lock_floor_pct  = 30%
  profit_lock_basis      = FLOATING_EQUITY
  news_pre_event_window  = 30 minutes
  news_post_event_window = 30 minutes
  max_tick_staleness_ms  = 2000 ms

Production monetary limits remain UNDEFINED until set by operator.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class ProfitLockFormula(StrEnum):
    """LOCKED: PCT_RETRACE — percentage retracement from session peak profit."""
    PCT_RETRACE = "PCT_RETRACE"


class ProfitLockBasis(StrEnum):
    """LOCKED: FLOATING_EQUITY — profit lock uses current equity including floating PNL."""
    FLOATING_EQUITY = "FLOATING_EQUITY"


class DrawdownReference(StrEnum):
    """LOCKED: LIFETIME_HWM — drawdown measured from lifetime equity HWM."""
    LIFETIME_HWM = "LIFETIME_HWM"


class RiskConfig(BaseModel):
    """
    Risk Engine configuration model.

    LOCKED fields have approved defaults and must not change without an ADR.
    UNDEFINED fields default to None — engine returns NOT_CONFIGURED when None.
    """

    # ── UNDEFINED production monetary limits ──────────────────────────────
    daily_loss_limit_usd: Decimal | None = Field(
        default=None,
        description="Maximum allowed daily loss in USD. UNDEFINED.",
    )
    max_drawdown_usd: Decimal | None = Field(
        default=None,
        description="Maximum drawdown from lifetime HWM in USD. UNDEFINED.",
    )
    max_open_positions: int | None = Field(
        default=None,
        description="Maximum simultaneously open positions. UNDEFINED.",
    )
    max_open_lots: Decimal | None = Field(
        default=None,
        description="Maximum total open lot exposure across basket. UNDEFINED.",
    )
    max_spread_usd: Decimal | None = Field(
        default=None,
        description="Maximum acceptable spread in USD for XAUUSD. UNDEFINED.",
    )
    caution_drawdown_pct: Decimal | None = Field(
        default=None,
        description="Fraction of max_drawdown_usd that triggers CAUTION (e.g. 0.80 = 80%). UNDEFINED.",
    )


    # ── Position sizing (LOCKED: percentage-of-equity) ────────────────────
    risk_per_trade_pct: Decimal | None = Field(
        default=None,
        description="Risk per trade as fraction of equity (e.g. 0.01 = 1%). UNDEFINED.",
    )

    # Backward compatibility for legacy tests/code
    default_position_size_lots: Decimal | None = Field(
        default=None,
        description="Legacy fixed-lot fallback. None in production.",
    )

    # ── Profit lock (LOCKED formula, LOCKED baseline values) ─────────────
    profit_lock_formula: ProfitLockFormula = Field(
        default=ProfitLockFormula.PCT_RETRACE,
        description="LOCKED: PCT_RETRACE — percentage retracement from peak profit.",
    )
    profit_lock_basis: ProfitLockBasis = Field(
        default=ProfitLockBasis.FLOATING_EQUITY,
        description="LOCKED: FLOATING_EQUITY — includes unrealized PNL.",
    )
    profit_lock_threshold_usd: Decimal = Field(
        default=Decimal("10"),
        description="LOCKED baseline: activates at $10 session profit.",
    )
    profit_lock_floor_pct: Decimal = Field(
        default=Decimal("0.30"),
        description="LOCKED baseline: protect 30% of peak session profit.",
    )

    # ── Market data (LOCKED baseline) ─────────────────────────────────────
    max_tick_staleness_ms: int = Field(
        default=2000,
        description="LOCKED baseline: ticks older than 2000 ms are STALE.",
    )

    # ── News protection (LOCKED baseline) ─────────────────────────────────
    news_pre_event_window_minutes: int = Field(
        default=30,
        description="LOCKED baseline: block new entries 30 min before high-impact news.",
    )
    news_post_event_window_minutes: int = Field(
        default=30,
        description="LOCKED baseline: block new entries 30 min after high-impact news.",
    )

    # ── Session & Reference (LOCKED) ──────────────────────────────────────
    daily_reset_timezone: str = Field(
        default="UTC",
        description="LOCKED: daily session resets at 00:00 UTC.",
    )
    drawdown_reference: DrawdownReference = Field(
        default=DrawdownReference.LIFETIME_HWM,
        description="LOCKED: drawdown measured from lifetime equity HWM.",
    )

    # ── Emergency stop ─────────────────────────────────────────────────────
    emergency_stop_active: bool = Field(
        default=False,
        description="Manual emergency stop — overrides all other states.",
    )

    @property
    def is_fully_configured(self) -> bool:
        """True only when required trading parameters are explicitly set."""
        has_sizing = (self.risk_per_trade_pct is not None) or (self.default_position_size_lots is not None)
        return (
            self.daily_loss_limit_usd is not None
            and self.max_drawdown_usd is not None
            and self.max_open_positions is not None
            and has_sizing
        )

    @property
    def missing_parameters(self) -> list[str]:
        """Names of required parameters that are still UNDEFINED."""
        missing = []
        if self.daily_loss_limit_usd is None:
            missing.append("daily_loss_limit_usd")
        if self.max_drawdown_usd is None:
            missing.append("max_drawdown_usd")
        if self.max_open_positions is None:
            missing.append("max_open_positions")
        if self.risk_per_trade_pct is None and self.default_position_size_lots is None:
            missing.append("risk_per_trade_pct")
        return missing
