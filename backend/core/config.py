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
