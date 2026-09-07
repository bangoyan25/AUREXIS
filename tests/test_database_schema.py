"""
Tests for Database Schema & ORM Model Integrity.

Verifies:
1. All 14 tables registered in Base.metadata (5 initial/core + 9 trading domain).
2. Numeric columns have precision=18, scale=8.
3. Timestamp columns are timezone-aware.
4. Primary keys use UUID.
5. Foreign keys have correct ondelete policies.
6. Alembic migrations 001, 002, 003 parse without syntax errors.
7. Migration 003 has all 9 tables and critical columns matching ORM.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import Numeric
from sqlalchemy.dialects.postgresql import UUID

import backend.db.models  # noqa: F401 – registers all models
from backend.db.base import Base

EXPECTED_TABLES = {
    "users", "trading_accounts", "mt5_agents", "audit_logs",
    "refresh_tokens",
    "risk_configurations", "risk_decisions", "candidate_signals",
    "execution_commands", "execution_reports", "positions",
    "equity_snapshots", "daily_session_states", "news_events",
}


def test_all_14_tables_registered() -> None:
    registered = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - registered
    assert not missing, f"Missing from Base.metadata: {missing}"


def test_all_tables_have_uuid_primary_key() -> None:
    for tbl in EXPECTED_TABLES:
        table = Base.metadata.tables[tbl]
        pk_cols = list(table.primary_key.columns)
        assert len(pk_cols) == 1, f"{tbl}: expected 1 PK column, got {len(pk_cols)}"
        pk_col = pk_cols[0]
        assert pk_col.name == "id", f"{tbl}: PK column expected 'id', got {pk_col.name}"
        assert isinstance(pk_col.type, UUID), f"{tbl}: PK type expected UUID, got {type(pk_col.type)}"


def test_numeric_columns_precision_scale() -> None:
    monetary_tables = {
        "trading_accounts", "risk_configurations", "risk_decisions",
        "candidate_signals", "execution_commands", "execution_reports",
        "positions", "equity_snapshots", "daily_session_states",
    }
    for tbl in monetary_tables:
        table = Base.metadata.tables[tbl]
        for col in table.columns:
            if isinstance(col.type, Numeric):
                assert col.type.precision == 18, f"{tbl}.{col.name}: precision must be 18"
                assert col.type.scale == 8, f"{tbl}.{col.name}: scale must be 8"


def test_all_datetime_columns_timezone_aware() -> None:
    for tbl in EXPECTED_TABLES:
        table = Base.metadata.tables[tbl]
        for col in table.columns:
            if hasattr(col.type, "timezone"):
                assert col.type.timezone is True, (
                    f"{tbl}.{col.name}: DateTime must be timezone=True"
                )
def test_foreign_key_ondelete_policies() -> None:
    expected_rules = {
        ("trading_accounts", "users"): "CASCADE",
        ("mt5_agents", "trading_accounts"): "CASCADE",
        ("refresh_tokens", "users"): "CASCADE",
        ("risk_configurations", "trading_accounts"): "CASCADE",
        ("equity_snapshots", "trading_accounts"): "CASCADE",
        ("daily_session_states", "trading_accounts"): "CASCADE",
        ("audit_logs", "users"): "SET NULL",
        ("audit_logs", "trading_accounts"): "SET NULL",
        ("audit_logs", "mt5_agents"): "SET NULL",
        ("risk_decisions", "trading_accounts"): "SET NULL",
        ("candidate_signals", "trading_accounts"): "SET NULL",
        ("execution_commands", "trading_accounts"): "SET NULL",
        ("execution_commands", "candidate_signals"): "SET NULL",
        ("execution_commands", "risk_decisions"): "SET NULL",
        ("execution_reports", "execution_commands"): "SET NULL",
        ("execution_reports", "trading_accounts"): "SET NULL",
        ("positions", "trading_accounts"): "SET NULL",
        ("positions", "execution_commands"): "SET NULL",
    }
    for (child, parent), expected_ondelete in expected_rules.items():
        tbl = Base.metadata.tables[child]
        fks = [fk for fk in tbl.foreign_keys if fk.column.table.name == parent]
        assert fks, f"No FK from {child} to {parent}"
        for fk in fks:
            assert (fk.ondelete or "").upper() == expected_ondelete, (
                f"FK {child}->{parent} ondelete expected {expected_ondelete}"
            )


def test_migrations_syntax_valid() -> None:
    versions = Path("migrations/versions")
    for py_file in versions.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        code = py_file.read_text(encoding="utf-8")
        try:
            ast.parse(code)
        except SyntaxError as exc:
            pytest.fail(f"Syntax error in {py_file.name}: {exc}")


def test_migration_003_covers_all_9_trading_domain_tables() -> None:
    migration_003 = Path("migrations/versions/003_trading_domain.py").read_text(encoding="utf-8")
    domain_tables = [
        "risk_configurations", "risk_decisions", "candidate_signals",
        "execution_commands", "execution_reports", "positions",
        "equity_snapshots", "daily_session_states", "news_events",
    ]
    for table_name in domain_tables:
        assert f'"{table_name}"' in migration_003, f"Table {table_name} missing from migration 003"
    assert "profit_lock_floor_usd" in migration_003
    assert "fill_volume_lots" in migration_003
    assert "executed_at" in migration_003
    assert "idempotency_key" in migration_003
    assert "raw_broker_response_json" in migration_003


def test_alembic_upgrade_head_offline_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify full migration chain to head generates valid SQL without schema errors."""
    import contextlib
    import io

    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:testpass@localhost:5432/railway")
    monkeypatch.delenv("ALEMBIC_DATABASE_URL", raising=False)

    buf = io.StringIO()
    cfg = Config("alembic.ini")
    with contextlib.redirect_stdout(buf):
        command.upgrade(cfg, "head", sql=True)

    sql_output = buf.getvalue()
    assert "CREATE TABLE execution_commands" in sql_output
    assert "003_trading_domain" in sql_output

