"""Strategy Engine State table.

Revision ID: 005_strategy_engine_state
Revises: 004_mt5_agent_commands
Create Date: 2026-09-10

Adds strategy_engine_state table for Phase 4B:
- Per-account strategy on/off control (enabled, dry_run)
- Cooldown tracking via last_signal_candle_ts
- Signal observability (last_signal_direction, last_signal_at, last_risk_decision)
- One-position limit enforced at service layer via open_position_count
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_strategy_engine_state"
down_revision: str | None = "004_mt5_agent_commands"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)
_UUID_PK = dict(primary_key=True, server_default=sa.text("uuid_generate_v4()"), nullable=False)
_TS = sa.DateTime(timezone=True)
_TS_NOW = dict(server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "strategy_engine_state",
        sa.Column("id", _UUID, **_UUID_PK),
        sa.Column(
            "account_id",
            _UUID,
            sa.ForeignKey("trading_accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("strategy_id", sa.String(100), nullable=False, server_default="AUREXIS_CORE"),
        sa.Column("strategy_version", sa.String(50), nullable=False, server_default="AUREXIS-STRAT-1.0.0"),
        sa.Column("symbol", sa.String(20), nullable=False, server_default="XAUUSD"),
        sa.Column("timeframe", sa.String(10), nullable=False, server_default="M15"),
        # Signal observability — last evaluated signal
        sa.Column("last_signal_direction", sa.String(10), nullable=True),
        sa.Column("last_signal_at", _TS, nullable=True),
        sa.Column("last_signal_candle_ts", _TS, nullable=True),
        sa.Column("last_signal_id", _UUID, nullable=True),
        sa.Column("last_signal_reason", sa.String(200), nullable=True),
        # Risk Gate last decision
        sa.Column("last_risk_decision", sa.String(20), nullable=True),
        sa.Column("last_risk_reason_code", sa.String(100), nullable=True),
        # Execution last outcome
        sa.Column("last_execution_status", sa.String(30), nullable=True),
        sa.Column("created_at", _TS, **_TS_NOW),
        sa.Column("updated_at", _TS, **_TS_NOW),
    )
    op.create_index(
        "ix_strategy_engine_state_account_id",
        "strategy_engine_state",
        ["account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_strategy_engine_state_account_id", table_name="strategy_engine_state")
    op.drop_table("strategy_engine_state")
