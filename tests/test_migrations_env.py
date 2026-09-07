"""
Regression tests for migrations/env.py:get_database_url().

Verifies URL resolution precedence, normalization, and error behavior.
All tests manipulate os.environ directly via monkeypatch.

Precedence:
  1. ALEMBIC_DATABASE_URL — explicit override, highest priority.
  2. DATABASE_URL         — Railway PostgreSQL plugin provides this.
  3. RuntimeError         — no usable URL found; fail clearly.
"""

from __future__ import annotations

import sys

import pytest


def _get_database_url() -> str:
    """Import and call get_database_url() from migrations.env."""
    if "migrations.env" in sys.modules:
        del sys.modules["migrations.env"]
    from migrations.env import get_database_url  # noqa: PLC0415
    return get_database_url()


@pytest.fixture(autouse=True)
def _clean_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all database URL variables from os.environ for each test."""
    monkeypatch.delenv("ALEMBIC_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_SYNC_URL", raising=False)


@pytest.mark.unit
class TestAlembicDatabaseUrlPrecedence:
    """ALEMBIC_DATABASE_URL takes precedence over DATABASE_URL."""

    def test_alembic_url_used_when_both_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", "postgresql://explicit:pw@host:5432/db")
        monkeypatch.setenv("DATABASE_URL", "postgresql://fallback:pw@other:5432/db")
        url = _get_database_url()
        assert url == "postgresql://explicit:pw@host:5432/db"
        assert "fallback" not in url

    def test_database_url_used_when_alembic_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host:5432/db")
        url = _get_database_url()
        assert url == "postgresql://user:pw@host:5432/db"

    def test_database_url_used_when_alembic_is_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", "")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host:5432/db")
        url = _get_database_url()
        assert url == "postgresql://user:pw@host:5432/db"


@pytest.mark.unit
class TestAlembicDatabaseUrlNormalization:
    """URL scheme normalization for Alembic sync driver compatibility."""

    def test_postgres_scheme_normalized_to_postgresql(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Railway provides postgres:// (legacy scheme); normalize to postgresql://."""
        monkeypatch.setenv("DATABASE_URL", "postgres://user:pw@host:5432/db")
        url = _get_database_url()
        assert url == "postgresql://user:pw@host:5432/db"
        assert not url.startswith("postgres://")

    def test_postgresql_scheme_passthrough(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """postgresql:// is already correct — returned unchanged."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host:5432/db")
        url = _get_database_url()
        assert url == "postgresql://user:pw@host:5432/db"

    def test_asyncpg_prefix_stripped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """postgresql+asyncpg:// stripped to postgresql:// for psycopg2."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pw@host:5432/db")
        url = _get_database_url()
        assert url == "postgresql://user:pw@host:5432/db"
        assert "asyncpg" not in url

    def test_asyncpg_prefix_stripped_via_alembic_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Normalization also applies to ALEMBIC_DATABASE_URL input."""
        monkeypatch.setenv(
            "ALEMBIC_DATABASE_URL", "postgresql+asyncpg://user:pw@host:5432/db"
        )
        url = _get_database_url()
        assert url == "postgresql://user:pw@host:5432/db"

    def test_aiosqlite_prefix_collapsed_to_sqlite(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """postgresql+aiosqlite:// (test override) collapsed to sqlite:///."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+aiosqlite:///test.db")
        url = _get_database_url()
        assert url.startswith("sqlite:///")

    def test_postgres_alembic_override_normalized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """postgres:// in ALEMBIC_DATABASE_URL also normalized."""
        monkeypatch.setenv("ALEMBIC_DATABASE_URL", "postgres://user:pw@host:5432/db")
        url = _get_database_url()
        assert url == "postgresql://user:pw@host:5432/db"


@pytest.mark.unit
class TestAlembicDatabaseUrlErrors:
    """Missing URL → clear RuntimeError; no silent fake/default URL."""

    def test_raises_when_no_url_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RuntimeError raised when neither variable is set."""
        with pytest.raises(RuntimeError) as exc_info:
            _get_database_url()
        assert "DATABASE_URL" in str(exc_info.value)

    def test_error_message_guides_railway_users(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Error message mentions DATABASE_URL so Railway users find the fix."""
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            _get_database_url()

    def test_does_not_return_fake_default_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No invented placeholder URL is ever returned when config is missing."""
        with pytest.raises(RuntimeError):
            _get_database_url()

