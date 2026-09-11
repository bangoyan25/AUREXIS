"""Create licenses table (licensing skeleton).

Revision ID: 007
Down revision: 006

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "licenses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("license_key", sa.String(256), nullable=False),
        sa.Column("plan", sa.String(64), nullable=False, server_default="demo"),
        sa.Column("feature_strategy_engine", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("feature_brain", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("feature_backtest", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("feature_multi_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_licenses_license_key", "licenses", ["license_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_licenses_license_key", table_name="licenses")
    op.drop_table("licenses")
