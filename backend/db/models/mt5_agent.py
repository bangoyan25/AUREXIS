"""
MT5Agent model.

One MT5Agent = one EA instance connecting to the backend for a specific account.
Each agent has a unique identity and secret for HMAC authentication.
An agent may only execute commands for its registered account.

The EA is execution-only. It does not generate signals or modify risk state.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.db.models.account import TradingAccount


class MT5Agent(TimestampMixin, Base):
    __tablename__ = "mt5_agents"

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

    # Human-readable identifier for logs
    label: Mapped[str] = mapped_column(String(100), nullable=False)

    # Authentication: each agent has a unique shared secret (HMAC)
    # Stored as bcrypt hash — never plaintext
    hashed_secret: Mapped[str] = mapped_column(String(255), nullable=False)

    # Connection state — PostgreSQL is authoritative.
    # Redis may cache live state for fast reads.
    # After a Redis restart, read last_known_status from here and treat
    # UNKNOWN as DISCONNECTED until the agent sends a fresh heartbeat.
    # Safe default: unknown connection state → no execution allowed.
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_known_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="UNKNOWN",
        # Possible values: UNKNOWN | CONNECTED | DISCONNECTED | ERROR
        # UNKNOWN and CONNECTED-but-unverified must both block new execution
        # until a fresh heartbeat confirms live connection.
    )

    # MT5 version reported by the EA
    mt5_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ea_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    account: Mapped[TradingAccount] = relationship(
        "TradingAccount", back_populates="mt5_agents"
    )

    def __repr__(self) -> str:
        return f"<MT5Agent id={self.id} label={self.label!r} account_id={self.account_id}>"
