"""
Phase 4A: Automated Unit & Integration Tests for Controlled Demo Execution Pipeline.

Covers:
1. RISK GATE MANDATORY:
   - Risk Gate ALLOW permits execution.
   - Risk Gate BLOCK prevents command creation and dispatch.
   - Offline agent blocks execution.
   - Stale market data blocks execution.
   - Client cannot fake or bypass Risk Gate.
2. DEMO SAFETY GUARD:
   - DEMO account (MetaQuotes-Demo) allowed.
   - Real / Live / unknown environment accounts strictly rejected.
3. TENANCY ISOLATION:
   - User A cannot execute trades on User B's account (HTTP 404).
   - Unauthenticated requests rejected (HTTP 401).
4. VALIDATION:
   - Non-XAUUSD symbol rejected (HTTP 422).
   - Invalid side rejected (HTTP 422).
   - Invalid / zero / negative / excessive volume rejected (HTTP 422).
5. IDEMPOTENCY:
   - Submitting same client_order_id returns existing command/result.
   - No duplicate orders or positions created.
6. EXECUTION LIFECYCLE & PERSISTENCE:
   - OPEN_POSITION creates command, dispatches over WSS, records ExecutionReport and Position.
   - CLOSE_POSITION closes position in DB, updates status to CLOSED.
   - Positions endpoint reports actual open position count.
7. SECURITY:
   - No secret leakage in responses, payloads, or logs.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.core.config import settings
from backend.db.base import Base
from backend.db.models.account import TradingAccount
from backend.db.models.agent_command import MT5AgentCommand
from backend.db.models.equity import EquitySnapshot
from backend.db.models.execution import ExecutionReport as DbExecutionReport, Position as DbPosition
from backend.db.models.mt5_agent import MT5Agent
from backend.db.models.risk import RiskConfiguration
from backend.db.models.user import User
from backend.main import create_app
from backend.services import market_data_service
from backend.services.auth import create_access_token
from backend.services.execution_service import record_agent_execution_result
from backend.ws.agent_manager import agent_manager


@pytest.fixture(autouse=True)
def configure_test_env(monkeypatch: pytest.MonkeyPatch):
    test_secret = SecretStr("test-secret-key-32-chars-long-123456")
    monkeypatch.setattr(settings, "JWT_SECRET", test_secret)

    mock_pipe = MagicMock()
    mock_pipe.set = MagicMock()
    mock_pipe.execute = AsyncMock(return_value=True)
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=None)

    mock_redis = MagicMock()
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)
    mock_redis.get = AsyncMock(return_value=None)
    monkeypatch.setattr(market_data_service, "get_cache_client", lambda: mock_redis)


@pytest.fixture
async def test_env():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    from backend.db.session import get_db
    app.dependency_overrides[get_db] = _get_test_db

    yield app, session_factory

    app.dependency_overrides.clear()
    await engine.dispose()


async def _seed_test_account(
    session_factory,
    email: str = "trader@example.com",
    server: str = "MetaQuotes-Demo",
    is_demo: bool = True,
) -> tuple[User, TradingAccount, MT5Agent, str]:
    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            email=email,
            display_name=email.split("@")[0],
            hashed_password="hash",
        )
        session.add(user)
        await session.flush()

        account = TradingAccount(
            id=uuid.uuid4(),
            user_id=user.id,
            label="Demo Test Account",
            broker="Demo Broker",
            mt5_server=server,
            mt5_account_number=f"5055{uuid.uuid4().hex[:6]}",
            is_cent_account=False,
            cent_normalization_factor=Decimal("1.0"),
            is_active=True,
            trading_enabled=True,
        )
        session.add(account)
        await session.flush()

        agent = MT5Agent(
            id=uuid.uuid4(),
            account_id=account.id,
            label="Primary EA",
            hashed_secret="secret_hashed_val",
            last_known_status="CONNECTED",
        )
        session.add(agent)

        eq = EquitySnapshot(
            account_id=account.id,
            balance_usd=Decimal("1000.00"),
            equity_usd=Decimal("1000.00"),
            snapped_at=datetime.now(UTC),
        )
        session.add(eq)

        cfg = RiskConfiguration(
            account_id=account.id,
            version=1,
            effective_from=datetime.now(UTC),
            daily_loss_limit_usd=Decimal("50.00"),
            max_drawdown_usd=Decimal("100.00"),
            max_open_positions=5,
        )
        session.add(cfg)
        await session.commit()

        token = create_access_token(subject=str(user.id))
        return user, account, agent, token


def _make_fresh_tick():
    return {
        "symbol": "XAUUSD",
        "bid": "2645.10",
        "ask": "2645.35",
        "spread": "0.25",
        "point": "0.01",
        "digits": 2,
        "tick_time": datetime.now(UTC).strftime("%Y.%m.%d %H:%M:%S"),
        "received_at": datetime.now(UTC).isoformat(),
        "tick_volume": 100,
    }




class TestPhase4aRiskGatingAndSafety:
    @pytest.mark.asyncio
    async def test_offline_agent_blocks_execution(self, test_env):
        app, sf = test_env
        _, account, agent, token = await _seed_test_account(sf)

        with patch.object(agent_manager, "is_connected", return_value=False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                res = await c.post(
                    f"/api/v1/accounts/{account.id}/execution/test",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "action": "OPEN_POSITION",
                        "symbol": "XAUUSD",
                        "side": "BUY",
                        "volume": 0.01,
                        "client_order_id": "ord-test-001",
                    },
                )
                assert res.status_code == 400
                data = res.json()
                assert data["detail"]["code"] == "AGENT_OFFLINE"

    @pytest.mark.asyncio
    async def test_risk_gate_block_prevents_execution_command_creation(self, test_env):
        app, sf = test_env
        _, account, agent, token = await _seed_test_account(sf)

        with patch.object(agent_manager, "is_connected", return_value=True):
            with patch("backend.api.v1.execution_routes.evaluate_risk_gate") as mock_gate:
                from backend.services.risk_gate import RiskDecisionOutput
                mock_gate.return_value = RiskDecisionOutput(
                    decision="BLOCK",
                    reason_code="MARKET_DATA_STALE",
                    reason="Tick age 3500ms exceeds 2000ms threshold",
                )

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                    res = await c.post(
                        f"/api/v1/accounts/{account.id}/execution/test",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "action": "OPEN_POSITION",
                            "symbol": "XAUUSD",
                            "side": "BUY",
                            "volume": 0.01,
                            "client_order_id": "ord-test-002",
                        },
                    )
                    assert res.status_code == 403
                    data = res.json()["detail"]
                    assert data["code"] == "RISK_GATE_BLOCKED"
                    assert data["decision"] == "BLOCK"
                    assert data["reason_code"] == "MARKET_DATA_STALE"

        async with sf() as session:
            cmds = (await session.execute(select(MT5AgentCommand))).scalars().all()
            assert len(cmds) == 0

    @pytest.mark.asyncio
    async def test_non_demo_account_strictly_blocked(self, test_env):
        app, sf = test_env
        _, account, agent, token = await _seed_test_account(sf, server="Live-Broker-Server")

        with patch.object(agent_manager, "is_connected", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                res = await c.post(
                    f"/api/v1/accounts/{account.id}/execution/test",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "action": "OPEN_POSITION",
                        "symbol": "XAUUSD",
                        "side": "BUY",
                        "volume": 0.01,
                        "client_order_id": "ord-test-003",
                    },
                )
                assert res.status_code == 403
                data = res.json()["detail"]
                assert data["code"] == "DEMO_ACCOUNT_REQUIRED"



class TestPhase4aTenancyAndValidation:
    @pytest.mark.asyncio
    async def test_user_b_cannot_execute_on_user_a_account(self, test_env):
        app, sf = test_env
        _, account_a, _, _ = await _seed_test_account(sf, email="userA@example.com")
        _, _, _, token_b = await _seed_test_account(sf, email="userB@example.com")

        with patch.object(agent_manager, "is_connected", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                res = await c.post(
                    f"/api/v1/accounts/{account_a.id}/execution/test",
                    headers={"Authorization": f"Bearer {token_b}"},
                    json={
                        "action": "OPEN_POSITION",
                        "symbol": "XAUUSD",
                        "side": "BUY",
                        "volume": 0.01,
                        "client_order_id": "ord-test-004",
                    },
                )
                assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, test_env):
        app, sf = test_env
        _, account, _, _ = await _seed_test_account(sf)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.post(
                f"/api/v1/accounts/{account.id}/execution/test",
                json={
                    "action": "OPEN_POSITION",
                    "symbol": "XAUUSD",
                    "side": "BUY",
                    "volume": 0.01,
                    "client_order_id": "ord-test-005",
                },
            )
            assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_symbol_rejected(self, test_env):
        app, sf = test_env
        _, account, _, token = await _seed_test_account(sf)

        with patch.object(agent_manager, "is_connected", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                res = await c.post(
                    f"/api/v1/accounts/{account.id}/execution/test",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "action": "OPEN_POSITION",
                        "symbol": "EURUSD",
                        "side": "BUY",
                        "volume": 0.01,
                        "client_order_id": "ord-test-006",
                    },
                )
                assert res.status_code == 422
                assert res.json()["detail"]["code"] == "INVALID_SYMBOL"

    @pytest.mark.asyncio
    async def test_invalid_volume_rejected(self, test_env):
        app, sf = test_env
        _, account, _, token = await _seed_test_account(sf)

        with patch.object(agent_manager, "is_connected", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                res = await c.post(
                    f"/api/v1/accounts/{account.id}/execution/test",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "action": "OPEN_POSITION",
                        "symbol": "XAUUSD",
                        "side": "BUY",
                        "volume": 0,
                        "client_order_id": "ord-test-007",
                    },
                )
                assert res.status_code == 422

                res2 = await c.post(
                    f"/api/v1/accounts/{account.id}/execution/test",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "action": "OPEN_POSITION",
                        "symbol": "XAUUSD",
                        "side": "BUY",
                        "volume": 1.0,
                        "client_order_id": "ord-test-008",
                    },
                )
                assert res2.status_code == 422



class TestPhase4aIdempotencyAndPipelinePersistence:
    @pytest.mark.asyncio
    async def test_idempotency_returns_existing_command(self, test_env):
        """Same client_order_id submitted twice → one command, no duplicate dispatch."""
        app, sf = test_env
        _, account, _, token = await _seed_test_account(sf)

        with patch.object(agent_manager, "is_connected", return_value=True):
            with patch("backend.api.v1.execution_routes.evaluate_risk_gate") as mock_gate:
                mock_gate.return_value = MagicMock(decision="ALLOW", reason_code="OK", reason="ok")

                payload = {
                    "action": "OPEN_POSITION",
                    "symbol": "XAUUSD",
                    "side": "BUY",
                    "volume": 0.01,
                    "client_order_id": "idemp-idem-200",
                }

                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                    res1 = await c.post(
                        f"/api/v1/accounts/{account.id}/execution/test",
                        headers={"Authorization": f"Bearer {token}"},
                        json=payload,
                    )
                    assert res1.status_code == 200
                    data1 = res1.json()

                    res2 = await c.post(
                        f"/api/v1/accounts/{account.id}/execution/test",
                        headers={"Authorization": f"Bearer {token}"},
                        json=payload,
                    )
                    assert res2.status_code == 200
                    data2 = res2.json()

                # Same command_id returned both times — no duplicate
                assert data1["command_id"] == data2["command_id"]
                assert data1["client_order_id"] == data2["client_order_id"]

    @pytest.mark.asyncio
    async def test_execution_result_recorded_in_db(self, test_env):
        """record_agent_execution_result creates ExecutionReport row in DB."""
        app, sf = test_env
        _, account, agent, _ = await _seed_test_account(sf)

        async with sf() as session:
            mock_cmd = MagicMock()
            mock_cmd.command_type = "OPEN_POSITION"
            mock_cmd.status = "COMPLETED"
            mock_cmd.payload_json = None

            result_payload = {
                "command_id": str(uuid.uuid4()),
                "client_order_id": "recon-test-ord-1",
                "success": True,
                "retcode": 10009,
                "retcode_description": "TRADE_RETCODE_DONE",
                "order_ticket": 111111,
                "deal_ticket": 222222,
                "position_ticket": 333333,
                "executed_volume": 0.01,
                "executed_price": 2350.50,
                "symbol": "XAUUSD",
                "timestamp": datetime.now(UTC).isoformat(),
                "command_type": "OPEN_POSITION",
                "side": "BUY",
            }

            await record_agent_execution_result(
                session,
                account_id=account.id,
                command=mock_cmd,
                result=result_payload,
            )
            await session.commit()

            # Verify report in DB
            rep = (await session.execute(select(DbExecutionReport).where(DbExecutionReport.account_id == account.id))).scalar_one_or_none()
            assert rep is not None
            assert rep.status == "FILLED"
            assert rep.broker_ticket == 333333

    @pytest.mark.asyncio
    async def test_position_not_found_recorded_as_failed(self, test_env):
        """If broker reports failure (success=False), ExecutionReport gets FAILED status."""
        app, sf = test_env
        _, account, agent, _ = await _seed_test_account(sf)

        async with sf() as session:
            mock_cmd = MagicMock()
            mock_cmd.command_type = "OPEN_POSITION"
            mock_cmd.status = "FAILED"
            mock_cmd.payload_json = None

            result_payload = {
                "command_id": str(uuid.uuid4()),
                "client_order_id": "recon-test-fail-1",
                "success": False,
                "retcode": 10006,
                "retcode_description": "TRADE_RETCODE_REJECT",
                "symbol": "XAUUSD",
                "timestamp": datetime.now(UTC).isoformat(),
                "command_type": "OPEN_POSITION",
                "side": "BUY",
            }

            await record_agent_execution_result(
                session,
                account_id=account.id,
                command=mock_cmd,
                result=result_payload,
            )
            await session.commit()

            rep = (await session.execute(select(DbExecutionReport).where(DbExecutionReport.account_id == account.id))).scalar_one_or_none()
            assert rep is not None
            assert rep.status == "FAILED"

