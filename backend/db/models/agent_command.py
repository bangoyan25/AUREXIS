"""MT5AgentCommand model.

Control-plane commands sent to MT5 Execution Agents.
Lifecycle: PENDING -> SENT -> ACKNOWLEDGED -> COMPLETED | FAILED
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.db.models.mt5_agent import MT5Agent


class MT5AgentCommand(TimestampMixin, Base):
    __tablename__ = "mt5_agent_commands"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="uuid_generate_v4()",
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mt5_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    command_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        index=True,
    )
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    agent: Mapped[MT5Agent] = relationship(
        "MT5Agent", back_populates="commands"
    )

    __table_args__ = (
        Index("ix_mt5_agent_commands_agent_status", "agent_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<MT5AgentCommand id={self.id} agent_id={self.agent_id} type={self.command_type} status={self.status}>"
