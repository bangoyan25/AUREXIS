"""Licensing DB model.

Phase skeleton — tracks which features (Strategy Engine, Brain, etc.) are
enabled per account or instance.  Production enforcement is not wired here;
this model exists to record the intent and provide a future policy hook.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from backend.db.base import Base


class License(Base):
    """Instance-level feature licensing record."""

    __tablename__ = "licenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_key = Column(String(256), nullable=False, unique=True, index=True)
    plan = Column(String(64), nullable=False, default="demo")

    # Per-feature flags
    feature_strategy_engine = Column(Boolean, nullable=False, default=True)
    feature_brain            = Column(Boolean, nullable=False, default=True)
    feature_backtest         = Column(Boolean, nullable=False, default=True)
    feature_multi_account    = Column(Boolean, nullable=False, default=False)

    # Validity
    valid_from  = Column(DateTime(timezone=True), nullable=True, default=None)
    valid_until = Column(DateTime(timezone=True), nullable=True, default=None)
    revoked     = Column(Boolean, nullable=False, default=False)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

