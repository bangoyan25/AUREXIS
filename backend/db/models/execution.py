"""
SQLAlchemy models for Execution Commands, Reports, and Positions.

- ExecutionCommand: command dispatched to MT5 agent.
- ExecutionReport: asynchronous execution result returned by MT5 agent.
- Position: authoritative open and historical position tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, ImmutableTimestampMixin, TimestampMixin


class ExecutionCommand(ImmutableTimestampMixin, Base):
    """Execution command authorized by Risk Engine and dispatched to MT5 Agent."""
    __tablename__ = "execution_commands"

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
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_signals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    risk_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    order_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    volume_lots: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    slippage_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    magic_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="CREATED", index=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account = relationship("TradingAccount")
    signal = relationship("CandidateSignal")
    risk_decision = relationship("RiskDecision")


class ExecutionReport(ImmutableTimestampMixin, Base):
    """Execution report received from MT5 EA detailing broker order fulfillment.

    Columns match docs/DATABASE_SCHEMA.md §3.5 (authoritative spec) plus
    `idempotency_key` and `raw_broker_response_json` added for service-layer
    correlation and debugging without conflicting with the spec.

    `executed_at` is the canonical timestamp name.  `reported_at` is provided
    as a Python property alias so existing service / test code keeps working
    without a SQL column rename.
    """
    __tablename__ = "execution_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="uuid_generate_v4()",
    )
    command_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("execution_commands.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trading_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # idempotency_key: optional back-reference to the originating command key
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    broker_ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    broker_deal_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fill_price: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    # fill_volume_lots: canonical name per spec.  Property alias `filled_lots` preserved.
    fill_volume_lots: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    slippage_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commission_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    swap_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    broker_error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    broker_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # raw_broker_response_json: full broker response blob for debugging
    raw_broker_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # executed_at: canonical timestamp per spec (replaces earlier `reported_at` column name)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Python-level compat aliases (no extra DB columns)
    @property
    def reported_at(self) -> datetime:
        """Alias for `executed_at` — retained for backward compat."""
        return self.executed_at

    @property
    def filled_lots(self) -> Decimal | None:
        """Alias for `fill_volume_lots` — retained for backward compat."""
        return self.fill_volume_lots

    account = relationship("TradingAccount")
    command = relationship("ExecutionCommand")


class Position(TimestampMixin, Base):
    """Authoritative record of an open or closed MT5 position."""
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("account_id", "broker_ticket", name="uq_positions_account_ticket"),
    )

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
    command_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("execution_commands.id", ondelete="SET NULL"),
        nullable=True,
    )
    broker_ticket: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    lots: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=8), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=8), nullable=False)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    take_profit: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    unrealized_pnl_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    commission_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    swap_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    magic_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN", index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    realized_pnl_usd: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account = relationship("TradingAccount")
    command = relationship("ExecutionCommand")
