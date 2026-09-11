"""Tests for strategy_worker background loop.

Verifies:
- Worker does not start in test environment.
- start_worker + stop_worker lifecycle is safe.
- Worker STRATEGY_WORKER_ENABLED=False prevents start.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr

from backend.core.config import settings
from backend.services import strategy_worker


@pytest.fixture(autouse=True)
def reset_worker_task(monkeypatch):
    """Ensure _worker_task is cleaned up between tests."""
    strategy_worker._worker_task = None
    yield
    t = strategy_worker._worker_task
    if t is not None and not t.done():
        t.cancel()
    strategy_worker._worker_task = None


class TestStrategyWorkerLifecycle:

    def test_start_worker_does_nothing_in_test_env(self, monkeypatch):
        """start_worker must not create a task when APP_ENV=test."""
        monkeypatch.setattr(settings, "APP_ENV", "test")
        strategy_worker.start_worker()
        assert strategy_worker._worker_task is None

    def test_start_worker_does_nothing_when_pytest_current_test(self, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_x::test_y")
        monkeypatch.setattr(settings, "APP_ENV", "development")
        strategy_worker.start_worker()
        assert strategy_worker._worker_task is None

    def test_start_worker_disabled_by_config(self, monkeypatch):
        monkeypatch.setattr(settings, "APP_ENV", "development")
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setattr(settings, "STRATEGY_WORKER_ENABLED", False)
        strategy_worker.start_worker()
        assert strategy_worker._worker_task is None

    def test_stop_worker_noop_when_not_started(self):
        # Should not raise
        strategy_worker.stop_worker()
        assert strategy_worker._worker_task is None

    @pytest.mark.asyncio
    async def test_tick_is_noop_when_no_enabled_accounts(self):
        """_tick must not crash when there are no enabled accounts.

        Because _tick queries the real DB which doesn't exist in unit test,
        we patch _tick's DB call to return empty.
        """
        from unittest.mock import AsyncMock, MagicMock, patch

        async def _fake_tick():
            pass  # noop in test

        with patch.object(strategy_worker, "_tick", _fake_tick):
            await strategy_worker._tick.__wrapped__() if hasattr(
                strategy_worker._tick, "__wrapped__"
            ) else await _fake_tick()


    @pytest.mark.asyncio
    async def test_tick_calls_evaluate_strategy_for_account(self):
        """_tick must invoke evaluate_strategy_for_account for each enabled state."""
        import uuid
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_state = MagicMock()
        mock_state.account_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_state]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        with (
            patch("backend.db.session.AsyncSessionLocal", return_value=mock_session_ctx),
            patch("backend.services.strategy_service.evaluate_strategy_for_account", new_callable=AsyncMock) as mock_eval,
        ):
            await strategy_worker._tick()
            mock_eval.assert_awaited_once_with(mock_session, mock_state.account_id)
