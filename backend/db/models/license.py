"""Licensing DB model.

Subscription tiers:
- Tier 1: 30 days, 1 trading account
- Tier 2: 30 days, 5 trading accounts
- Tier 3: 30 days, unlimited trading accounts (-1)

States: UNUSED, ACTIVE, EXPIRED, REVOKED
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.db.models.user import User


class License(Base):
    """User/instance subscription license with serial code and account limit."""

    __tablename__ = "licenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_key = Column(String(256), nullable=False, unique=True, index=True)
    serial_code = Column(String(128), nullable=True, unique=True, index=True)
    tier = Column(Integer, nullable=False, default=1)  # 1, 2, 3
    plan = Column(String(64), nullable=False, default="demo")
    status = Column(String(32), nullable=False, default="UNUSED", index=True)  # UNUSED, ACTIVE, EXPIRED, REVOKED
    account_limit = Column(Integer, nullable=False, default=1)  # 1 (T1), 5 (T2), -1 (T3 = unlimited)

    # Per-feature flags
    feature_strategy_engine = Column(Boolean, nullable=False, default=True)
    feature_brain            = Column(Boolean, nullable=False, default=True)
    feature_backtest         = Column(Boolean, nullable=False, default=True)
    feature_multi_account    = Column(Boolean, nullable=False, default=False)

    # User attachment
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Validity timestamps
    issued_at   = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
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

    user: Mapped[User | None] = relationship("User", back_populates="licenses")

    def is_currently_valid(self, now: datetime | None = None) -> bool:
        """Check if license is currently valid and not revoked/expired."""
        from datetime import UTC
        curr = now or datetime.now(UTC)
        if self.revoked or self.status in ("REVOKED", "EXPIRED"):
            return False
        if self.valid_until and self.valid_until < curr:
            return False
        return self.status == "ACTIVE"


