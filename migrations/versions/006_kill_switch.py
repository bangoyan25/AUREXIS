"""Add kill_switch_active to risk_configurations.

Revision ID: 006
Down revision: 005_strategy_engine_state
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005_strategy_engine_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "risk_configurations",
        sa.Column("kill_switch_active", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("risk_configurations", "kill_switch_active")
