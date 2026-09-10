"""
SQLAlchemy models for Account Equity and Daily Session states.

- EquitySnapshot: historical snapshots of balance/equity for HWM and drawdown calculations.
- DailySessionState: per-account per-date tracking for daily loss and profit-lock.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, ImmutableTimestampMixin


class EquitySnapshot(ImmutableTimestampMixin, Base):
    """Immutable point-in-time snapshot of account balance and equity."""
    __tablename__ = "equity_snapshots"

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
    balance_usd: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=8), nullable=False)
    equity_usd: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=8), nullable=False)
    margin_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    free_margin_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    floating_pnl_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    open_position_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    account = relationship("TradingAccount")


class DailySessionState(ImmutableTimestampMixin, Base):
    """Per-account per-date state for daily loss limits and profit-lock threshold tracking."""
    __tablename__ = "daily_session_states"
    __table_args__ = (
        UniqueConstraint("account_id", "session_date", name="uq_daily_session_account_date"),
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
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    session_open_equity_usd: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=8), nullable=False)
    session_peak_profit_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False, default=Decimal("0")
    )
    realized_pnl_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=8), nullable=False, default=Decimal("0")
    )
    floating_pnl_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    daily_loss_stop_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    profit_lock_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    profit_lock_floor_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    profit_lock_activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    account = relationship("TradingAccount")
