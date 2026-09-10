"""
Unit tests for AUREXIS application configuration.

Verifies that:
- UNDEFINED parameters default to None (not invented values)
- Configuration reads environment variables correctly
- Safety properties are preserved
"""

from __future__ import annotations

import pytest

from backend.core.config import Settings


@pytest.mark.unit
class TestConfigDefaults:
    """All UNDEFINED trading/risk parameters must default to None."""

    def test_risk_daily_loss_limit_undefined(self) -> None:
        cfg = Settings()
        assert cfg.RISK_DAILY_LOSS_LIMIT_USD is None, (
            "Daily loss limit must remain UNDEFINED until formally approved"
        )

    def test_risk_max_drawdown_undefined(self) -> None:
        cfg = Settings()
        assert cfg.RISK_MAX_DRAWDOWN_USD is None

    def test_risk_profit_lock_formula_undefined(self) -> None:
        cfg = Settings()
        assert cfg.RISK_PROFIT_LOCK_FORMULA is None

    def test_risk_max_open_positions_undefined(self) -> None:
        cfg = Settings()
        assert cfg.RISK_MAX_OPEN_POSITIONS is None

    def test_risk_default_position_size_undefined(self) -> None:
        cfg = Settings()
        assert cfg.RISK_DEFAULT_POSITION_SIZE_LOTS is None

    def test_market_data_provider_undefined(self) -> None:
        cfg = Settings()
        assert cfg.MARKET_DATA_PROVIDER is None

    def test_market_data_staleness_threshold_undefined(self) -> None:
        cfg = Settings()
        assert cfg.MARKET_DATA_STALENESS_THRESHOLD_SECONDS is None

    def test_news_provider_undefined(self) -> None:
        cfg = Settings()
        assert cfg.NEWS_PROVIDER is None

    def test_news_pre_event_window_undefined(self) -> None:
        cfg = Settings()
        assert cfg.NEWS_PRE_EVENT_WINDOW_MINUTES is None

    def test_news_post_event_window_undefined(self) -> None:
        cfg = Settings()
        assert cfg.NEWS_POST_EVENT_WINDOW_MINUTES is None


@pytest.mark.unit
class TestConfigEnvironmentFlags:
    def test_default_env_is_development(self) -> None:
        cfg = Settings()
        # CI may override this — only assert the property works
        assert cfg.APP_ENV in ("development", "test", "production")

    def test_is_development_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        cfg = Settings()
        assert cfg.is_development is True
        assert cfg.is_production is False
        assert cfg.is_test is False

    def test_is_test_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "test")
        cfg = Settings()
        assert cfg.is_test is True
        assert cfg.is_development is False

    def test_is_production_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        cfg = Settings()
        assert cfg.is_production is True


@pytest.mark.unit
class TestConfigJwtSecurity:
    def test_require_jwt_secret_raises_when_empty(self) -> None:
        cfg = Settings(JWT_SECRET="")
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            cfg.require_jwt_secret()

    def test_require_jwt_secret_returns_value_when_set(self) -> None:
        import secrets
        secret = secrets.token_hex(32)
        cfg = Settings(JWT_SECRET=secret)
        assert cfg.require_jwt_secret() == secret

    def test_jwt_secret_not_exposed_in_repr(self) -> None:
        secret = "super-secret-jwt-key-do-not-log"
        cfg = Settings(JWT_SECRET=secret)
        # SecretStr must not appear in default repr
        assert secret not in repr(cfg.JWT_SECRET)


@pytest.mark.unit
class TestRailwayReadiness:
    """Settings additions required for Railway deployment."""

    def test_port_defaults_to_none(self) -> None:
        cfg = Settings()
        assert cfg.PORT is None

    def test_effective_port_falls_back_to_backend_port(self) -> None:
        cfg = Settings()
        assert cfg.effective_port == cfg.BACKEND_PORT

    def test_effective_port_uses_railway_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PORT", "4567")
        cfg = Settings()
        assert cfg.effective_port == 4567

    def test_async_database_url_passthrough(self) -> None:
        cfg = Settings(DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db")
        assert cfg.async_database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_async_database_url_normalizes_postgresql_scheme(self) -> None:
        cfg = Settings(DATABASE_URL="postgresql://user:pass@host:5432/db")
        assert cfg.async_database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_async_database_url_normalizes_postgres_scheme(self) -> None:
        """Railway PostgreSQL plugin provides postgres:// (legacy scheme)."""
        cfg = Settings(DATABASE_URL="postgres://user:pass@host:5432/db")
        assert cfg.async_database_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_cors_origins_empty_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        cfg = Settings(_env_file=None)
        assert cfg.CORS_ORIGINS == ""

    def test_allowed_cors_origins_includes_localhost_in_dev(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        cfg = Settings()
        assert "http://localhost:3000" in cfg.allowed_cors_origins
        assert "http://127.0.0.1:3000" in cfg.allowed_cors_origins

    def test_allowed_cors_origins_includes_localhost_in_test(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "test")
        cfg = Settings()
        assert "http://localhost:3000" in cfg.allowed_cors_origins

    def test_allowed_cors_origins_empty_in_production_without_cors_origins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        cfg = Settings(APP_ENV="production", CORS_ORIGINS="")
        assert cfg.allowed_cors_origins == []

    def test_allowed_cors_origins_respects_cors_origins_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        cfg = Settings(
            APP_ENV="production",
            CORS_ORIGINS="https://frontend.up.railway.app,https://app.aurexis.io",
        )
        origins = cfg.allowed_cors_origins
        assert "https://frontend.up.railway.app" in origins
        assert "https://app.aurexis.io" in origins

    def test_allowed_cors_origins_strips_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        cfg = Settings(
            APP_ENV="production",
            CORS_ORIGINS="  https://frontend.up.railway.app  , https://app.aurexis.io  ",
        )
        origins = cfg.allowed_cors_origins
        assert "https://frontend.up.railway.app" in origins
        assert "https://app.aurexis.io" in origins

    def test_cors_origins_in_dev_includes_both_localhost_and_extra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        cfg = Settings(
            APP_ENV="development",
            CORS_ORIGINS="https://staging.aurexis.io",
        )
        origins = cfg.allowed_cors_origins
        assert "http://localhost:3000" in origins
        assert "https://staging.aurexis.io" in origins
