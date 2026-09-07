"""
AUREXIS application configuration.

All configuration is loaded from environment variables.
Never hardcode secrets or trading parameters here.

UNDEFINED trading/risk parameters are represented as Optional fields
that default to None. Components that require these values must check
for None and enter NOT_CONFIGURED state rather than using invented defaults.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Railway injects PORT as the assigned listener port for each service.
# BACKEND_PORT is the local/default override.
# The canonical start command should use: --port ${PORT:-8000}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    APP_NAME: str = "AUREXIS"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # ── Backend server ─────────────────────────────────────────────────────
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    PORT: int | None = Field(
        default=None,
        description="Railway or cloud provider assigned dynamic port (PORT env var)",
    )
    CORS_ORIGINS: str = Field(
        default="",
        description="Comma-separated allowed CORS origins for production",
    )

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://aurexis:change-me-locally@localhost:5432/aurexis",
        description="Async SQLAlchemy database URL (asyncpg driver)",
    )
    DATABASE_SYNC_URL: str = Field(
        default="postgresql://aurexis:change-me-locally@localhost:5432/aurexis",
        description="Sync database URL for Alembic",
    )

    # ── Redis ──────────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    REDIS_CACHE_DB: int = 0
    REDIS_PUBSUB_DB: int = 1

    # ── Authentication ─────────────────────────────────────────────────────
    JWT_SECRET: SecretStr = Field(
        default=SecretStr(""),
        description="JWT signing secret — generate with: python -c \"import secrets; print(secrets.token_hex(32))\"",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    ENCRYPTION_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="Application-level field encryption key",
    )

    # ── MT5 Agent ──────────────────────────────────────────────────────────
    MT5_AGENT_SECRET_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="Shared secret for MT5 agent HMAC authentication",
    )
    MT5_PUSH_ENDPOINT: str | None = None

    # ── Market Data ────────────────────────────────────────────────────────
    # UNDEFINED — do not set defaults here
    MARKET_DATA_PROVIDER: str | None = None
    MARKET_DATA_API_KEY: SecretStr | None = None
    MARKET_DATA_STALENESS_THRESHOLD_SECONDS: int | None = None  # UNDEFINED

    # ── News Engine ────────────────────────────────────────────────────────
    # UNDEFINED — do not set defaults here
    NEWS_PROVIDER: str | None = None
    NEWS_API_KEY: SecretStr | None = None
    NEWS_PRE_EVENT_WINDOW_MINUTES: int | None = None   # UNDEFINED
    NEWS_POST_EVENT_WINDOW_MINUTES: int | None = None  # UNDEFINED

    # ── FX Rate ────────────────────────────────────────────────────────────
    FX_RATE_PROVIDER: str | None = None
    FX_RATE_API_KEY: SecretStr | None = None

    # ── Risk Engine ────────────────────────────────────────────────────────
    # ALL UNDEFINED — must remain None until formally approved by user.
    # Risk Engine will return NOT_CONFIGURED for any None required value.
    # Stored as Decimal to avoid float precision errors when fed to RiskConfig.
    RISK_DAILY_LOSS_LIMIT_USD: Decimal | None = None        # UNDEFINED
    RISK_MAX_DRAWDOWN_USD: Decimal | None = None            # UNDEFINED
    RISK_PROFIT_LOCK_FORMULA: str | None = None             # UNDEFINED
    RISK_MAX_OPEN_POSITIONS: int | None = None              # UNDEFINED
    RISK_DEFAULT_POSITION_SIZE_LOTS: Decimal | None = None  # UNDEFINED

    # ── Frontend ───────────────────────────────────────────────────────────
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"
    NEXT_PUBLIC_API_BASE_URL: str | None = Field(
        default=None,
        description="Railway backend URL for frontend (alias for NEXT_PUBLIC_API_URL)",
    )
    NEXT_PUBLIC_WS_URL: str = "ws://localhost:8000"

    # ── Derived properties ─────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_test(self) -> bool:
        return self.APP_ENV == "test"

    @property
    def effective_port(self) -> int:
        """Return Railway PORT if set, otherwise BACKEND_PORT."""
        return self.PORT if self.PORT is not None else self.BACKEND_PORT

    @property
    def async_database_url(self) -> str:
        """
        Return asyncpg-compatible database URL.
        Converts standard postgresql:// or postgres:// (supplied by Railway / cloud providers)
        into postgresql+asyncpg:// scheme required by SQLAlchemy async engine.
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url[len("postgresql://"):]
        if url.startswith("postgres://"):
            return "postgresql+asyncpg://" + url[len("postgres://"):]
        return url

    @property
    def allowed_cors_origins(self) -> list[str]:
        """
        Return allowed CORS origins.
        Localhost always allowed in development and test modes.
        Production origins supplied via CORS_ORIGINS (comma-separated).
        """
        origins: list[str] = []
        if self.is_development or self.is_test:
            origins.extend(["http://localhost:3000", "http://127.0.0.1:3000"])
        if self.CORS_ORIGINS:
            for item in self.CORS_ORIGINS.split(","):
                stripped = item.strip()
                if stripped and stripped not in origins:
                    origins.append(stripped)
        return origins

    def require_jwt_secret(self) -> str:
        """
        Raise if JWT secret is not configured.

        This is the ONLY safe way to retrieve the JWT signing secret.
        It raises RuntimeError if the secret is empty or missing.
        Never use JWT_SECRET.get_secret_value() directly — always call this method.
        """
        val = self.JWT_SECRET.get_secret_value()
        if not val:
            raise RuntimeError(
                "JWT_SECRET is not configured. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return val


# Single global settings instance.
# Tests override by monkeypatching or by providing a .env.test.
settings = Settings()
