"""
Alembic environment configuration for AUREXIS.

Uses async SQLAlchemy engine for normal operations and sync engine
for autogenerate / offline mode.
"""

from __future__ import annotations

import asyncio
import logging
import os
from logging.config import fileConfig

from alembic import context
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection

# ── Import all models so Alembic autogenerate can detect them ──────────────
from backend.db.base import Base  # noqa: F401
from backend.db.models.account import TradingAccount  # noqa: F401
from backend.db.models.audit_log import AuditLog  # noqa: F401
from backend.db.models.mt5_agent import MT5Agent  # noqa: F401
from backend.db.models.refresh_token import RefreshToken  # noqa: F401
from backend.db.models.user import User  # noqa: F401

# ── Alembic config ─────────────────────────────────────────────────────────
# context.config is only populated when Alembic CLI runs this file.
# When migrations/env.py is imported directly (e.g. in unit tests to test
# get_database_url()), context.config does not exist — guard the attribute access.
try:
    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)
except AttributeError:
    # Not running under Alembic CLI — skip config/logging setup.
    config = None  # type: ignore[assignment]

# All models share one Base (single registry) — one metadata object for Alembic.
target_metadata = Base.metadata

log = logging.getLogger("alembic.env")


def get_database_url() -> str:
    """
    Resolve the database URL for Alembic (synchronous psycopg2 driver).

    Precedence:
      1. ALEMBIC_DATABASE_URL — explicit override, highest priority.
      2. DATABASE_URL         — Railway PostgreSQL plugin provides this automatically.
      3. RuntimeError         — no usable URL found; fail clearly.

    Normalization applied:
      - postgresql+asyncpg://  →  postgresql://   (strip asyncpg prefix)
      - postgresql+aiosqlite:// →  sqlite:///      (test/in-memory SQLite)
      - postgres://            →  postgresql://    (Railway/Heroku legacy scheme)

    Diagnostics emitted (NO credentials, usernames, passwords, or secrets logged):
      - ALEMBIC_DATABASE_URL configured: yes / no
      - DATABASE_URL configured: yes / no
      - Selected source: ALEMBIC_DATABASE_URL / DATABASE_URL
    """
    # Load .env if present — does NOT overwrite variables already in the environment.
    # Priority is therefore: real env vars (Railway / Docker / shell) > .env > defaults.
    # In Railway production the .env file is absent and all variables come from os.environ.
    # In local development the .env file populates variables not already set in the shell.
    #
    # AUREXIS_SKIP_DOTENV=1 suppresses .env loading.  Set only in test fixtures that need
    # full os.environ isolation (tests/test_migrations_env.py).  Never set in production.
    if os.environ.get("AUREXIS_SKIP_DOTENV") != "1":
        load_dotenv(find_dotenv(usecwd=True), override=False)

    alembic_url = os.environ.get("ALEMBIC_DATABASE_URL") or ""
    database_url = os.environ.get("DATABASE_URL") or ""
    postgres_url = os.environ.get("POSTGRES_URL") or ""
    database_public_url = os.environ.get("DATABASE_PUBLIC_URL") or ""
    database_sync_url = os.environ.get("DATABASE_SYNC_URL") or ""

    pghost = os.environ.get("PGHOST") or ""
    pguser = os.environ.get("PGUSER") or ""
    pgpassword = os.environ.get("PGPASSWORD") or ""
    pgport = os.environ.get("PGPORT") or "5432"
    pgdatabase = os.environ.get("PGDATABASE") or ""

    # ── Diagnostics (safe — no credentials logged) ──────────────────────────
    log.info(
        "Alembic database URL resolution: "
        "ALEMBIC_DATABASE_URL configured=%s, "
        "DATABASE_URL configured=%s, "
        "POSTGRES_URL configured=%s, "
        "DATABASE_PUBLIC_URL configured=%s, "
        "DATABASE_SYNC_URL configured=%s, "
        "PGHOST configured=%s",
        "yes" if alembic_url else "no",
        "yes" if database_url else "no",
        "yes" if postgres_url else "no",
        "yes" if database_public_url else "no",
        "yes" if database_sync_url else "no",
        "yes" if pghost else "no",
    )

    # ── Precedence ──────────────────────────────────────────────────────────
    if alembic_url:
        raw = alembic_url
        selected_source = "ALEMBIC_DATABASE_URL"
    elif database_url:
        raw = database_url
        selected_source = "DATABASE_URL"
    elif postgres_url:
        raw = postgres_url
        selected_source = "POSTGRES_URL"
    elif database_public_url:
        raw = database_public_url
        selected_source = "DATABASE_PUBLIC_URL"
    elif database_sync_url:
        raw = database_sync_url
        selected_source = "DATABASE_SYNC_URL"
    elif pghost and pguser and pgdatabase:
        raw = f"postgresql://{pguser}:{pgpassword}@{pghost}:{pgport}/{pgdatabase}"
        selected_source = "PGHOST/PGUSER/PGDATABASE"
    else:
        raise RuntimeError(
            "No database URL configured for Alembic migrations. "
            "Set DATABASE_URL in Railway backend service Variables "
            "(reference Railway PostgreSQL: ${{Postgres.DATABASE_URL}} or ${{PostgreSQL.DATABASE_URL}}). "
            "Neither DATABASE_URL, ALEMBIC_DATABASE_URL, POSTGRES_URL, nor PGHOST is set."
        )

    log.info("Alembic database URL selected source: %s", selected_source)

    url = raw
    # Strip asyncpg prefix — Alembic uses psycopg2 sync driver
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    # Strip aiosqlite prefix — collapse to plain sqlite:// for in-memory tests
    url = url.replace("postgresql+aiosqlite://", "sqlite:///")
    # Normalize legacy postgres:// scheme (Railway / Heroku)
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
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


# Only execute migrations when invoked by the Alembic CLI runner (config is present).
# Prevents execution when env.py is imported in unit tests or diagnostic scripts.
if config is not None:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
