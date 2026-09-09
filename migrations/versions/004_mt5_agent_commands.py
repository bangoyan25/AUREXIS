"""MT5 Agent Commands table.

Revision ID: 004_mt5_agent_commands
Revises: 003_trading_domain
Create Date: 2026-09-08

Adds the mt5_agent_commands table for control-plane command lifecycle:
- id UUID primary key
- agent_id FK -> mt5_agents.id CASCADE
- command_type VARCHAR(50) PING | GET_STATUS
- status VARCHAR(30) PENDING | SENT | ACKNOWLEDGED | COMPLETED | FAILED | EXPIRED
- payload_json TEXT nullable (request payload, must never contain agent_secret)
- result_json TEXT nullable (EA response)
- error_message VARCHAR(500) nullable
- sent_at / acknowledged_at / completed_at TIMESTAMP WITH TIME ZONE nullable
- created_at / updated_at standard TIMESTAMP WITH TIME ZONE

Indexes:
- ix_mt5_agent_commands_agent_id_status (agent_id, status)
- ix_mt5_agent_commands_status (status)
- ix_mt5_agent_commands_agent_id (agent_id)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_mt5_agent_commands"
down_revision: str | None = "003_trading_domain"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)
_UUID_PK = dict(primary_key=True, server_default=sa.text("uuid_generate_v4()"), nullable=False)
_TS = sa.DateTime(timezone=True)
_TS_NOW = dict(server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "mt5_agent_commands",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column(
            "agent_id",
            _UUID,
            sa.ForeignKey("mt5_agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("command_type", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("payload_json", sa.Text, nullable=True),
        sa.Column("result_json", sa.Text, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("sent_at", _TS, nullable=True),
        sa.Column("acknowledged_at", _TS, nullable=True),
        sa.Column("completed_at", _TS, nullable=True),
        sa.Column("created_at", _TS, **_TS_NOW),
        sa.Column("updated_at", _TS, **_TS_NOW),
    )
    op.create_index(
        "ix_mt5_agent_commands_agent_id",
        "mt5_agent_commands",
        ["agent_id"],
    )
    op.create_index(
        "ix_mt5_agent_commands_status",
        "mt5_agent_commands",
        ["status"],
    )
    op.create_index(
        "ix_mt5_agent_commands_agent_id_status",
        "mt5_agent_commands",
        ["agent_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_mt5_agent_commands_agent_id_status", table_name="mt5_agent_commands")
    op.drop_index("ix_mt5_agent_commands_status", table_name="mt5_agent_commands")
    op.drop_index("ix_mt5_agent_commands_agent_id", table_name="mt5_agent_commands")
    op.drop_table("mt5_agent_commands")
