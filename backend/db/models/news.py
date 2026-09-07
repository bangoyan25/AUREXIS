"""
SQLAlchemy model for News Events (economic calendar).

- NewsEvent: normalized macroeconomic release schedule.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, ImmutableTimestampMixin


class NewsEvent(ImmutableTimestampMixin, Base):
    """
    Normalized economic calendar release for news protection filter.
    """
    __tablename__ = "news_events"
    __table_args__ = (
        UniqueConstraint("source", "source_event_id", name="uq_news_events_source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="uuid_generate_v4()",
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    event_name: Mapped[str] = mapped_column(String(500), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    impact: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # HIGH, MEDIUM, LOW
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    pre_event_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    post_event_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    forecast_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
