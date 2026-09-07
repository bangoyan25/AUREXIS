"""
SQLAlchemy declarative base for AUREXIS.

All database models must import from this module to register
with the metadata used by Alembic autogenerate.

Two mixin classes are provided (both attached to one DeclarativeBase):
- TimestampMixin: created_at + updated_at (for mutable models)
- ImmutableTimestampMixin: created_at only (for append-only models like AuditLog)

All concrete models inherit from Base (single DeclarativeBase) plus the
appropriate mixin. This keeps all models in one registry so relationships resolve.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ── Single shared registry ─────────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    Single declarative base for all AUREXIS database models.

    All models (mutable and immutable) share this registry so that
    cross-model relationships (e.g. AuditLog.user) resolve correctly.

    Mutable models: add TimestampMixin
    Immutable/append-only models: add ImmutableTimestampMixin

    Base itself provides no columns — each mixin provides the timestamps.
    """

    def __repr__(self) -> str:
        pk_cols = [c.name for c in self.__table__.primary_key.columns]  # type: ignore[attr-defined]
        pk_vals = {col: getattr(self, col, "?") for col in pk_cols}
        pk_str = ", ".join(f"{k}={v!r}" for k, v in pk_vals.items())
        return f"<{self.__class__.__name__} {pk_str}>"


# ── Timestamp mixins ───────────────────────────────────────────────────────

class TimestampMixin:
    """
    Mixin for mutable models: created_at + updated_at.

    Add to all models that may be updated after creation.
    Both columns use server_default=func.now() (UTC).
    updated_at is refreshed on every UPDATE via onupdate.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImmutableTimestampMixin:
    """
    Mixin for append-only models: created_at only, NO updated_at.

    Use this for AuditLog and any other table that must never be modified.
    The deliberate absence of updated_at (and its onupdate trigger) is a
    correctness guarantee — not an oversight.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ── Convenience aliases ───────────────────────────────────────────────────
# Kept for backward-compatibility in imports (e.g. `from backend.db.base import ImmutableBase`)
# ImmutableBase is a Base subclass with no columns of its own — it is abstract.

class ImmutableBase(Base):
    """
    Abstract base for append-only models. Inherits from Base (shared registry).
    Concrete models also inherit ImmutableTimestampMixin.

    This alias exists so `from backend.db.base import ImmutableBase` works for
    isinstance() checks and migration import patterns.
    """
    __abstract__ = True

