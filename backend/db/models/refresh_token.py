"""
RefreshToken model.

Tracks active refresh token JTIs for revocation support.
One row per active session — revoked or expired rows are inert.

Design:
- jti (JWT ID) is the unique identifier; stored as-is (UUID string from the JWT payload).
- user_id FK allows bulk revocation (e.g. on password change).
- revoked_at: set on explicit logout or rotation; NULL means still active.
- expires_at: matches JWT exp claim — expired rows are never valid regardless of revoked_at.
- Only one DB row per issued refresh token; rotation inserts a new row.

Security: this table does not store the token itself — only the JTI.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base, ImmutableTimestampMixin


class RefreshToken(ImmutableTimestampMixin, Base):
    """
    Active / revoked refresh token registry.

    ImmutableTimestampMixin: no updated_at — revocation is represented
    by revoked_at column (set once, never changed after).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="uuid_generate_v4()",
    )

    # The JWT ID claim from the refresh token payload
    jti: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    # Owner — CASCADE delete means revoking the user also cleans up sessions
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Mirrors JWT exp — authoritative expiry; DB enforces this independently of JWT
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Set when explicitly revoked (logout or rotation); NULL = still active
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<RefreshToken jti={self.jti!r} user={self.user_id} "
            f"revoked={self.revoked_at is not None}>"
        )
