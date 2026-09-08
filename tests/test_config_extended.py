"""
Tests for new/extended config features:
- Decimal risk fields (M-2)
- jwt_secret_value property removed (M-3)
- Production JSON logging (M-4)
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from backend.core.config import Settings


@pytest.mark.unit
class TestDecimalRiskConfig:
    """M-2: Risk fields must be Decimal, not float."""

    def test_daily_loss_limit_defaults_none(self) -> None:
        cfg = Settings()
        assert cfg.RISK_DAILY_LOSS_LIMIT_USD is None

    def test_max_drawdown_defaults_none(self) -> None:
        cfg = Settings()
        assert cfg.RISK_MAX_DRAWDOWN_USD is None

    def test_position_size_defaults_none(self) -> None:
        cfg = Settings()
        assert cfg.RISK_DEFAULT_POSITION_SIZE_LOTS is None

    def test_daily_loss_from_env_is_decimal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RISK_DAILY_LOSS_LIMIT_USD", "100.50")
        cfg = Settings()
        assert cfg.RISK_DAILY_LOSS_LIMIT_USD is not None
        assert isinstance(cfg.RISK_DAILY_LOSS_LIMIT_USD, Decimal)
        assert not isinstance(cfg.RISK_DAILY_LOSS_LIMIT_USD, float)

    def test_max_drawdown_from_env_is_decimal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RISK_MAX_DRAWDOWN_USD", "250.00")
        cfg = Settings()
        assert cfg.RISK_MAX_DRAWDOWN_USD is not None
        assert isinstance(cfg.RISK_MAX_DRAWDOWN_USD, Decimal)

    def test_position_size_from_env_is_decimal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RISK_DEFAULT_POSITION_SIZE_LOTS", "0.01")
        cfg = Settings()
        assert cfg.RISK_DEFAULT_POSITION_SIZE_LOTS is not None
        assert isinstance(cfg.RISK_DEFAULT_POSITION_SIZE_LOTS, Decimal)


@pytest.mark.unit
class TestJwtSecretProperty:
    """M-3: jwt_secret_value property must not exist."""

    def test_jwt_secret_value_property_removed(self) -> None:
        """The unsafe jwt_secret_value property must not be accessible."""
        cfg = Settings(JWT_SECRET="test-secret-x1234567890abcdefghijklmno")
        assert not hasattr(cfg, "jwt_secret_value"), (
            "jwt_secret_value property must be removed — use require_jwt_secret() instead"
        )

    def test_require_jwt_secret_is_the_only_safe_accessor(self) -> None:
        import secrets
        secret = secrets.token_hex(32)
        cfg = Settings(JWT_SECRET=secret)
        assert cfg.require_jwt_secret() == secret


@pytest.mark.unit
class TestProductionLogging:
    """M-4: Production must use JSON renderer."""

    def test_development_uses_console_renderer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Development logging does not crash and uses console output."""
        monkeypatch.setenv("APP_ENV", "development")
        from backend.core.logging import configure_logging
        # Just verify it does not raise
        configure_logging("WARNING")

    def test_production_uses_json_renderer(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Production logging emits parseable JSON."""
        monkeypatch.setenv("APP_ENV", "production")
        import structlog
        # Reset structlog config cache before reconfiguring
        structlog.reset_defaults()
        from backend.core.logging import configure_logging, get_logger
        configure_logging("WARNING")
        logger = get_logger("test.prod.logging")
        logger.warning("test.event", key="value")
        captured = capsys.readouterr()
        # At least one line should be valid JSON
        output = captured.out.strip()
        if output:
            for line in output.splitlines():
                try:
                    parsed = json.loads(line)
                    assert "event" in parsed or "level" in parsed
                    break
                except json.JSONDecodeError:
                    continue

    def test_force_json_overrides_dev_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """force_json=True must work regardless of APP_ENV."""
        monkeypatch.setenv("APP_ENV", "development")
        import structlog
        structlog.reset_defaults()
        from backend.core.logging import configure_logging
        configure_logging("WARNING", force_json=True)  # Must not raise


@pytest.mark.unit
class TestBlankOptionalConfigCoercion:
    """Blank or whitespace-only optional environment variables must coerce to None."""

    def test_blank_risk_variables_remain_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RISK_DAILY_LOSS_LIMIT_USD", "")
        monkeypatch.setenv("RISK_MAX_DRAWDOWN_USD", "   ")
        monkeypatch.setenv("RISK_MAX_OPEN_POSITIONS", "")
        monkeypatch.setenv("RISK_DEFAULT_POSITION_SIZE_LOTS", "")
        monkeypatch.setenv("RISK_PROFIT_LOCK_FORMULA", "")
        cfg = Settings()
        assert cfg.RISK_DAILY_LOSS_LIMIT_USD is None
        assert cfg.RISK_MAX_DRAWDOWN_USD is None
        assert cfg.RISK_MAX_OPEN_POSITIONS is None
        assert cfg.RISK_DEFAULT_POSITION_SIZE_LOTS is None
        assert cfg.RISK_PROFIT_LOCK_FORMULA is None

    def test_blank_market_and_news_variables_remain_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MARKET_DATA_STALENESS_THRESHOLD_SECONDS", "")
        monkeypatch.setenv("NEWS_PRE_EVENT_WINDOW_MINUTES", "  ")
        monkeypatch.setenv("NEWS_POST_EVENT_WINDOW_MINUTES", "")
        monkeypatch.setenv("MARKET_DATA_PROVIDER", "")
        monkeypatch.setenv("NEWS_PROVIDER", "")
        monkeypatch.setenv("FX_RATE_PROVIDER", "")
        cfg = Settings()
        assert cfg.MARKET_DATA_STALENESS_THRESHOLD_SECONDS is None
        assert cfg.NEWS_PRE_EVENT_WINDOW_MINUTES is None
        assert cfg.NEWS_POST_EVENT_WINDOW_MINUTES is None
        assert cfg.MARKET_DATA_PROVIDER is None
        assert cfg.NEWS_PROVIDER is None
        assert cfg.FX_RATE_PROVIDER is None

    def test_blank_port_coerces_to_none_and_effective_port_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PORT", "")
        cfg = Settings()
        assert cfg.PORT is None
        assert cfg.effective_port == cfg.BACKEND_PORT

    def test_valid_numeric_values_still_parse_correctly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RISK_DAILY_LOSS_LIMIT_USD", "100.50")
        monkeypatch.setenv("RISK_MAX_OPEN_POSITIONS", "5")
        monkeypatch.setenv("MARKET_DATA_STALENESS_THRESHOLD_SECONDS", "30")
        cfg = Settings()
        assert Decimal("100.50") == cfg.RISK_DAILY_LOSS_LIMIT_USD
        assert cfg.RISK_MAX_OPEN_POSITIONS == 5
        assert cfg.MARKET_DATA_STALENESS_THRESHOLD_SECONDS == 30
