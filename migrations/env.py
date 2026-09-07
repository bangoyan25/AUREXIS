"""
Alembic environment configuration for AUREXIS.

Uses async SQLAlchemy engine for normal operations and sync engine
for autogenerate / offline mode.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection

# ── Import all models so Alembic autogenerate can detect them ──────────────
from backend.db.base import Base  # noqa: F401
from backend.db.models.account import TradingAccount  # noqa: F401
from backend.db.models.audit_log import AuditLog  # noqa: F401
from backend.db.models.mt5_agent import MT5Agent  # noqa: F401
from backend.db.models.refresh_token import RefreshToken  # noqa: F401

# Individual model imports — add new models here as they are created:
from backend.db.models.user import User  # noqa: F401

# ── Alembic config ─────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# All models share one Base (single registry) — one metadata object for Alembic.
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Resolve the database URL from environment.
    ALEMBIC_DATABASE_URL takes precedence (uses sync psycopg2 driver for Alembic).
    Falls back to DATABASE_SYNC_URL, then DATABASE_URL.
    Alembic requires a synchronous driver — strip 'async' variants.
    """
    url = (
        os.environ.get("ALEMBIC_DATABASE_URL")
        or os.environ.get("DATABASE_SYNC_URL")
        or os.environ.get("DATABASE_URL")
    )
    if not url:
        raise RuntimeError(
            "No database URL configured. "
            "Set ALEMBIC_DATABASE_URL in your .env file."
        )
    # Normalize: replace async driver prefix if present
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    # Normalize: replace legacy postgres:// scheme (Railway / Heroku style)
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    url = url.replace("postgresql+aiosqlite://", "sqlite:///")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live DB connection)."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against a live database using async engine."""
    url = get_database_url()
    # Alembic runs in sync context — use sync engine here
    from sqlalchemy import create_engine
    sync_engine = create_engine(url, poolclass=pool.NullPool)
    with sync_engine.connect() as connection:
        do_run_migrations(connection)
    sync_engine.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
