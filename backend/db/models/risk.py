"""
SQLAlchemy models for Risk configurations and decisions.

- RiskConfiguration: versioned risk configuration per trading account.
- RiskDecision: immutable audit trail of every authorization evaluation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, ImmutableTimestampMixin


class RiskConfiguration(ImmutableTimestampMixin, Base):
    """
    Versioned risk configuration for a trading account.
    Immutable once inserted — updates create a new version.
    """
    __tablename__ = "risk_configurations"
    __table_args__ = (
        UniqueConstraint("account_id", "version", name="uq_risk_config_account_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="uuid_generate_v4()",
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trading_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Core policy settings
    daily_reset_timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    drawdown_reference: Mapped[str] = mapped_column(String(50), nullable=False, default="LIFETIME_HWM")
    profit_lock_formula: Mapped[str] = mapped_column(String(50), nullable=False, default="PCT_RETRACE")
    profit_lock_basis: Mapped[str] = mapped_column(String(50), nullable=False, default="FLOATING_EQUITY")
    profit_lock_threshold_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False, default=Decimal("10")
    )
    profit_lock_floor_pct: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False, default=Decimal("0.30")
    )
    max_tick_staleness_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    news_pre_event_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    news_post_event_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    # Empirical risk limits (nullable until configured by user/trader)
    daily_loss_limit_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    max_drawdown_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    max_open_positions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_open_lots: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    max_spread_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    risk_per_trade_pct: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    kill_switch_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    account = relationship("TradingAccount")
    creator = relationship("User")


class RiskDecision(ImmutableTimestampMixin, Base):
    """
    Immutable audit record for every risk authorization evaluation.
    Every signal evaluation writes an entry regardless of approval/block.
    """
    __tablename__ = "risk_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="uuid_generate_v4()",
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trading_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    risk_config_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)  # APPROVED, BLOCKED
    reason_code: Mapped[str] = mapped_column(String(200), nullable=False)
    risk_state: Mapped[str] = mapped_column(String(50), nullable=False)

    equity_at_decision: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    drawdown_at_decision: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    daily_pnl_at_decision: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    profit_lock_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    profit_lock_floor_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    account = relationship("TradingAccount")
