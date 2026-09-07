"""
AuditLog model.

Immutable record of significant system events.
Audit records must not be modifiable through normal application flows.
All inserts are append-only — no UPDATE or DELETE is permitted on this table.

Inherits from ImmutableBase (not Base) — no updated_at field.
The occurred_at timestamp is set by the application at event time.
The created_at timestamp is set by the database server on insert.

Events recorded include (but are not limited to):
- Login / logout
- Account creation / modification
- Trading enable / disable
- Emergency stop
- Risk state change
- Signal generation
- Command creation / approval / rejection
- Execution result
- Reconciliation mismatch
- Configuration changes
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, ImmutableTimestampMixin

if TYPE_CHECKING:
    from backend.db.models.user import User


class AuditLog(ImmutableTimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="uuid_generate_v4()",
    )

    # Who
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Which account (if account-scoped event)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trading_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Which MT5 agent (if agent-scoped event)
    mt5_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mt5_agents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Event classification
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
        # Examples: USER_LOGIN, TRADING_ENABLED, RISK_STATE_CHANGED,
        #           EMERGENCY_STOP, COMMAND_CREATED, EXECUTION_RESULT,
        #           RECONCILIATION_MISMATCH, CONFIG_CHANGED
    )
    # Severity: INFO | WARNING | ERROR | CRITICAL
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")

    # Structured payload (JSON)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Correlation ID for tracing across the tick→signal→command→execution chain
    correlation_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )

    # IP address of the request (if applicable) — do NOT log passwords or secrets
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Audit event timestamp — set by the application, not by the client
    # created_at (from ImmutableBase) is set by DB server on insert
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships (read-only navigation)
    user: Mapped[User | None] = relationship(
        "User", back_populates="audit_logs"
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} event={self.event_type!r} "
            f"severity={self.severity!r} at={self.occurred_at}>"
        )
