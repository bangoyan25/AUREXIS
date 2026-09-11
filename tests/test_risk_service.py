"""
Tests for Risk Service and Position Sizing Policy — Phase C.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from backend.db.models.account import TradingAccount
from backend.db.models.equity import EquitySnapshot
from backend.db.models.risk import RiskConfiguration
from backend.db.models.risk import RiskDecision as RiskDecisionModel
from backend.db.models.user import User
from backend.risk.engine import MarketCondition
from backend.risk.sizing import FixedLotSizingPolicy, PercentageEquitySizingPolicy
from backend.risk.states import RiskState, SignalDecision
from backend.services.risk_service import (
    evaluate_and_record_risk,
)


def test_percentage_equity_sizing_calculation():
    sizing = PercentageEquitySizingPolicy(
        risk_per_trade_pct=Decimal("0.01"),  # 1%
        contract_size=Decimal("100"),
        min_lot=Decimal("0.01"),
        max_lot=Decimal("10.0"),
        lot_step=Decimal("0.01"),
    )
    # Equity = $10,000 -> 1% risk = $100.
    # Entry = 2000.00, SL = 1990.00 -> distance = $10.
    # Dollar risk per lot = 10 * 100 = 1,000 USD/lot.
    # Lots = 100 / 1000 = 0.10 lots.
    lots = sizing.calculate_lot_size(
        equity_usd=Decimal("10000"),
        entry_price=Decimal("2000.00"),
        stop_loss_price=Decimal("1990.00"),
    )
    assert lots == Decimal("0.10")


def test_percentage_equity_sizing_zero_or_invalid_stop():
    sizing = PercentageEquitySizingPolicy(risk_per_trade_pct=Decimal("0.01"))
    assert sizing.calculate_lot_size(Decimal("10000"), None, Decimal("1990.00")) is None
    assert sizing.calculate_lot_size(Decimal("10000"), Decimal("2000.00"), None) is None
    assert sizing.calculate_lot_size(Decimal("10000"), Decimal("2000.00"), Decimal("2000.00")) is None
    assert sizing.calculate_lot_size(Decimal("0"), Decimal("2000.00"), Decimal("1990.00")) is None


def test_percentage_equity_sizing_below_min_lot():
    sizing = PercentageEquitySizingPolicy(
        risk_per_trade_pct=Decimal("0.01"),
        min_lot=Decimal("0.01"),
    )
    # Equity = $10 -> 1% = $0.10 risk.
    # Distance = $10 -> risk per lot = $1000 -> lots = 0.0001 < 0.01 min lot.
    assert sizing.calculate_lot_size(Decimal("10"), Decimal("2000.00"), Decimal("1990.00")) is None


def test_fixed_lot_sizing():
    sizing = FixedLotSizingPolicy(fixed_lots=Decimal("0.05"))
    assert sizing.calculate_lot_size(Decimal("10000"), Decimal("2000"), Decimal("1990")) == Decimal("0.05")


@pytest.fixture
async def db_session():
    from sqlalchemy import StaticPool
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.db.base import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()



@pytest.mark.asyncio
async def test_risk_service_with_db_session(db_session):
    # 1. Create User and Trading Account
    user = User(
        email="trader_risk@example.com",
        hashed_password="test_hash",
        display_name="Trader",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    account = TradingAccount(
        user_id=user.id,
        label="Test Risk Account",
        broker="Test Broker",
        mt5_account_number="12345678",
        broker_currency="USD",
        cent_normalization_factor=Decimal("1.0"),
        trading_enabled=True,
    )
    db_session.add(account)
    await db_session.flush()

    # 2. Add Risk Configuration
    risk_conf = RiskConfiguration(
        account_id=account.id,
        version=1,
        effective_from=datetime.now(UTC),
        daily_loss_limit_usd=Decimal("50.00"),
        max_drawdown_usd=Decimal("100.00"),
        max_open_positions=3,
        max_open_lots=Decimal("1.00"),
        max_spread_usd=Decimal("0.50"),
        risk_per_trade_pct=Decimal("0.01"),
    )
    db_session.add(risk_conf)

    # 3. Add Equity Snapshot
    snapshot = EquitySnapshot(
        account_id=account.id,
        balance_usd=Decimal("1000.00"),
        equity_usd=Decimal("1000.00"),
        snapped_at=datetime.now(UTC),
    )
    db_session.add(snapshot)
    await db_session.commit()

    # 4. Evaluate risk via service
    decision = await evaluate_and_record_risk(
        session=db_session,
        account_id=account.id,
        market_condition=MarketCondition(spread=Decimal("0.20")),
        news_state="CLEAR",
    )

    assert decision.decision == SignalDecision.APPROVED
    assert decision.risk_state == RiskState.NORMAL
    assert decision.trading_allowed is True

    # 5. Verify persisted RiskDecision in DB
    from sqlalchemy import select
    res = await db_session.execute(
        select(RiskDecisionModel).where(RiskDecisionModel.account_id == account.id)
    )
    persisted = res.scalars().all()
    assert len(persisted) == 1
    assert persisted[0].decision == "APPROVED"
    assert persisted[0].reason_code == "ALL_CHECKS_PASSED"
