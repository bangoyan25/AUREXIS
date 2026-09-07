"""
Regression tests for migrations/env.py:get_database_url().

Verifies URL resolution precedence, normalization, error behavior,
safe diagnostic logging (no credentials), and async application URL integrity.

Precedence:
  1. ALEMBIC_DATABASE_URL — explicit override, highest priority.
  2. DATABASE_URL         — Railway PostgreSQL plugin provides this.
  3. RuntimeError         — no usable URL found; fail clearly.

Test classes:
  TestAlembicDatabaseUrlPrecedence    — ALEMBIC_DATABASE_URL > DATABASE_URL precedence
  TestAlembicDatabaseUrlNormalization — URL scheme normalization for psycopg2
  TestAlembicDatabaseUrlErrors        — clear failure with no credentials
  TestAlembicDatabaseUrlDiagnostics   — safe logging (no credentials in log output)
  TestAsyncApplicationUrlRemainsCorrect — settings.async_database_url stays correct
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


@pytest.mark.unit
class TestAlembicDatabaseUrlDiagnostics:
    """Safe diagnostic logging without credential exposure."""

    def test_diagnostics_emitted_for_database_url(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Diagnostic log shows configured status and selected source without credentials."""
        secret_password = "SuperSecretPassword123!"
        monkeypatch.setenv(
            "DATABASE_URL", f"postgresql://appuser:{secret_password}@postgres.railway.internal:5432/railway"
        )
        with caplog.at_level("INFO", logger="alembic.env"):
            url = _get_database_url()

        assert "postgresql://appuser:" in url
        # Verify diagnostic logs were generated
        log_text = caplog.text
        assert "Alembic database URL resolution:" in log_text
        assert "DATABASE_URL configured=yes" in log_text
        assert "ALEMBIC_DATABASE_URL configured=no" in log_text
        assert "selected source: DATABASE_URL" in log_text

        # CRITICAL: Secret credentials must NEVER appear in logs
        assert secret_password not in log_text
        assert "postgres.railway.internal" not in log_text

    def test_diagnostics_emitted_for_alembic_database_url(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Diagnostic log shows ALEMBIC_DATABASE_URL as selected source."""
        secret_token = "ultra_secret_token_abc987"
        monkeypatch.setenv(
            "ALEMBIC_DATABASE_URL",
            f"postgresql://migrator:{secret_token}@custom-host:5432/proddb",
        )
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://app:other_secret@postgres:5432/db"
        )
        with caplog.at_level("INFO", logger="alembic.env"):
            url = _get_database_url()

        assert "custom-host" in url
        log_text = caplog.text
        assert "Alembic database URL resolution:" in log_text
        assert "ALEMBIC_DATABASE_URL configured=yes" in log_text
        assert "DATABASE_URL configured=yes" in log_text
        assert "selected source: ALEMBIC_DATABASE_URL" in log_text

        # Secrets must NOT appear in log
        assert secret_token not in log_text
        assert "other_secret" not in log_text


@pytest.mark.unit
class TestAsyncApplicationUrlRemainsCorrect:
    """SQLAlchemy async application engine URL handling remains separate and intact."""

    def test_async_database_url_from_standard_postgresql(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """postgresql:// in Settings converts to postgresql+asyncpg:// for async engine."""
        from backend.core.config import Settings

        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@host:5432/dbname"
        )
        s = Settings()
        assert s.async_database_url == "postgresql+asyncpg://user:pass@host:5432/dbname"

    def test_async_database_url_from_legacy_postgres(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """postgres:// in Settings converts to postgresql+asyncpg:// for async engine."""
        from backend.core.config import Settings

        monkeypatch.setenv(
            "DATABASE_URL", "postgres://user:pass@host:5432/dbname"
        )
        s = Settings()
        assert s.async_database_url == "postgresql+asyncpg://user:pass@host:5432/dbname"

    def test_async_database_url_passthrough(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """postgresql+asyncpg:// remains unchanged."""
        from backend.core.config import Settings

        monkeypatch.setenv(
            "DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/dbname"
        )
        s = Settings()
        assert s.async_database_url == "postgresql+asyncpg://user:pass@host:5432/dbname"


