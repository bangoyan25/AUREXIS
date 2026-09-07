"""
Tests for Risk Engine position sizing and risk service.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.risk.config import RiskConfig
from backend.risk.sizing import FixedLotSizingPolicy, PercentageEquitySizingPolicy
from backend.risk.states import RiskState, SignalDecision
from backend.services.risk_service import (
    evaluate_and_record_risk,
    get_latest_risk_config,
)


def test_fixed_lot_sizing():
    policy = FixedLotSizingPolicy(fixed_lots=Decimal("0.05"))
    lots = policy.calculate_lot_size(
        equity_usd=Decimal("1000"),
        entry_price=Decimal("2000.00"),
        stop_loss_price=Decimal("1995.00"),
    )
    assert lots == Decimal("0.05")


def test_percentage_equity_sizing():
    policy = PercentageEquitySizingPolicy(
        risk_per_trade_pct=Decimal("0.01"),
        contract_size=Decimal("100"),
        min_lot=Decimal("0.01"),
        lot_step=Decimal("0.01"),
    )
    lots = policy.calculate_lot_size(
        equity_usd=Decimal("10000"),
        entry_price=Decimal("2000.00"),
        stop_loss_price=Decimal("1995.00"),
    )
    assert lots == Decimal("0.20")


def test_percentage_equity_sizing_missing_prices():
    policy = PercentageEquitySizingPolicy(risk_per_trade_pct=Decimal("0.01"))
    assert policy.calculate_lot_size(Decimal("10000"), None, Decimal("1995.00")) is None
    assert policy.calculate_lot_size(Decimal("10000"), Decimal("2000.00"), None) is None


def test_percentage_equity_sizing_zero_stop_distance():
    policy = PercentageEquitySizingPolicy(risk_per_trade_pct=Decimal("0.01"))
    assert policy.calculate_lot_size(Decimal("10000"), Decimal("2000.00"), Decimal("2000.00")) is None


def test_percentage_equity_sizing_below_min_lot():
    policy = PercentageEquitySizingPolicy(risk_per_trade_pct=Decimal("0.01"), min_lot=Decimal("0.01"))
    lots = policy.calculate_lot_size(Decimal("10"), Decimal("2000.00"), Decimal("1990.00"))
    assert lots is None


def test_percentage_equity_sizing_max_lot_cap():
    policy = PercentageEquitySizingPolicy(
        risk_per_trade_pct=Decimal("0.10"),
        max_lot=Decimal("1.00"),
    )
    lots = policy.calculate_lot_size(Decimal("100000"), Decimal("2000.00"), Decimal("1999.00"))
    assert lots == Decimal("1.00")


@pytest.mark.asyncio
async def test_get_latest_risk_config_default_when_empty():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    session.add = MagicMock()

    config = await get_latest_risk_config(session, uuid.uuid4())
    assert isinstance(config, RiskConfig)
    assert config.is_fully_configured is False


@pytest.mark.asyncio
async def test_evaluate_and_record_risk_service():
    session = AsyncMock()
    session.add = MagicMock()

    account_id = uuid.uuid4()

    # Mock empty config -> NOT_CONFIGURED
    mock_config_res = MagicMock()
    mock_config_res.scalar_one_or_none.return_value = None

    mock_eq_res = MagicMock()
    mock_eq_res.scalar_one_or_none.return_value = None

    mock_hwm_res = MagicMock()
    mock_hwm_res.scalar.return_value = Decimal("1000")

    mock_session_res = MagicMock()
    mock_session_res.scalar_one_or_none.return_value = None

    mock_pos_res = MagicMock()
    mock_pos_res.scalars.return_value.all.return_value = []

    session.execute.side_effect = [
        mock_config_res,
        mock_eq_res,
        mock_hwm_res,
        mock_session_res,
        mock_pos_res,
    ]

    with patch("backend.services.risk_service.record_audit_event", new_callable=AsyncMock) as mock_audit:
        decision = await evaluate_and_record_risk(
            session=session,
            account_id=account_id,
        )
        assert decision.decision == SignalDecision.NOT_CONFIGURED
        assert decision.risk_state == RiskState.NOT_CONFIGURED
        assert session.add.called
        assert session.commit.called
        assert mock_audit.called
