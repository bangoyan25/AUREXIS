"""
SQLAlchemy model for Strategy Engine State.

Phase 4B: Per-account strategy engine runtime state and control.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin


class StrategyEngineState(TimestampMixin, Base):
    """
    State and control record for an account's strategy engine instance.
    Controls whether automated signal generation and execution are active.
    """
    __tablename__ = "strategy_engine_state"

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
        unique=True,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(100), default="AUREXIS_CORE", nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(50), default="AUREXIS-STRAT-1.0.0", nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), default="XAUUSD", nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), default="M15", nullable=False)

    # Observability
    last_signal_direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_signal_candle_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_signal_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Risk gate
    last_risk_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_risk_reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Execution
    last_execution_status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    account = relationship("TradingAccount")
