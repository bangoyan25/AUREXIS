"""
SQLAlchemy model for Brain candidate signals.

- CandidateSignal: Brain proposed trading signal awaiting risk validation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, ImmutableTimestampMixin


class CandidateSignal(ImmutableTimestampMixin, Base):
    """
    Candidate signal produced by Brain pipeline.
    Represents an analytical proposal, NOT an execution command.
    """
    __tablename__ = "candidate_signals"

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
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, default="XAUUSD")
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY, SELL
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    regime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    setup_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    entry_reference: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    suggested_stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    suggested_take_profit: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    spread_at_signal: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=8), nullable=True)
    news_state_at_signal: Mapped[str | None] = mapped_column(String(50), nullable=True)
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="CANDIDATE_FORMING", index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account = relationship("TradingAccount")
