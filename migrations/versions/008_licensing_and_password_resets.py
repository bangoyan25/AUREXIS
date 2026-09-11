"""Licensing serial codes and password resets table.

Revision ID: 008
Down revision: 007

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Upgrade licenses table ──────────────────────────────────────────────
    op.add_column("licenses", sa.Column("serial_code", sa.String(128), nullable=True))
    op.add_column("licenses", sa.Column("tier", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("licenses", sa.Column("status", sa.String(32), nullable=False, server_default="UNUSED"))
    op.add_column("licenses", sa.Column("account_limit", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("licenses", sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("licenses", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "licenses",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_licenses_serial_code", "licenses", ["serial_code"], unique=True)
    op.create_index("ix_licenses_status", "licenses", ["status"])
    op.create_index("ix_licenses_user_id", "licenses", ["user_id"])

    # ── Create password_resets table ─────────────────────────────────────────
    op.create_table(
        "password_resets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])
    op.create_index("ix_password_resets_token_hash", "password_resets", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_password_resets_token_hash", table_name="password_resets")
    op.drop_index("ix_password_resets_user_id", table_name="password_resets")
    op.drop_table("password_resets")

    op.drop_index("ix_licenses_user_id", table_name="licenses")
    op.drop_index("ix_licenses_status", table_name="licenses")
    op.drop_index("ix_licenses_serial_code", table_name="licenses")
    op.drop_column("licenses", "user_id")
    op.drop_column("licenses", "activated_at")
    op.drop_column("licenses", "issued_at")
    op.drop_column("licenses", "account_limit")
    op.drop_column("licenses", "status")
    op.drop_column("licenses", "tier")
    op.drop_column("licenses", "serial_code")
