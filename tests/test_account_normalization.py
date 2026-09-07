"""
TradingAccount.normalize_to_usd regression tests.

Verifies that TradingAccount.normalize_to_usd() delegates to
normalize_broker_to_usd() and produces identical results:
- Decimal arithmetic only
- 2dp quantization (ROUND_HALF_EVEN)
- Consistent with the canonical service function
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from backend.services.normalization import (
    CENT_ACCOUNT_FACTOR,
    STANDARD_USD_FACTOR,
    normalize_broker_to_usd,
)


def make_account(factor: Decimal) -> MagicMock:
    """
    Minimal TradingAccount-like object for testing normalize_to_usd.
    Imports the real method to avoid testing a stub.
    """
    from backend.db.models.account import TradingAccount

    acct = MagicMock(spec=TradingAccount)
    acct.cent_normalization_factor = factor
    # Bind the real method to the mock object
    acct.normalize_to_usd = lambda v: TradingAccount.normalize_to_usd(acct, v)
    return acct


@pytest.mark.unit
class TestTradingAccountNormalizeToUsd:
    """Regression: TradingAccount.normalize_to_usd must match canonical service."""

    def test_cent_account_10000_equals_100_usd(self) -> None:
        acct = make_account(CENT_ACCOUNT_FACTOR)
        result = acct.normalize_to_usd(Decimal("10000"))
        expected = normalize_broker_to_usd(Decimal("10000"), CENT_ACCOUNT_FACTOR)
        assert result == expected
        assert result == Decimal("100.00")

    def test_standard_account_unchanged(self) -> None:
        acct = make_account(STANDARD_USD_FACTOR)
        result = acct.normalize_to_usd(Decimal("1234.56"))
        expected = normalize_broker_to_usd(Decimal("1234.56"), STANDARD_USD_FACTOR)
        assert result == expected
        assert result == Decimal("1234.56")

    def test_result_is_decimal_not_float(self) -> None:
        acct = make_account(CENT_ACCOUNT_FACTOR)
        result = acct.normalize_to_usd(Decimal("100"))
        assert isinstance(result, Decimal)
        assert not isinstance(result, float)

    def test_result_quantized_to_2dp(self) -> None:
        """Canonical service quantizes to 2dp — model method must match."""
        acct = make_account(CENT_ACCOUNT_FACTOR)
        result = acct.normalize_to_usd(Decimal("3"))
        # 3 * 0.01 = 0.03 — exactly 2dp
        assert result == Decimal("0.03")
        assert str(result) == "0.03"

    def test_negative_value_preserved(self) -> None:
        """Losses must maintain sign."""
        acct = make_account(CENT_ACCOUNT_FACTOR)
        result = acct.normalize_to_usd(Decimal("-500"))
        expected = normalize_broker_to_usd(Decimal("-500"), CENT_ACCOUNT_FACTOR)
        assert result == expected
        assert result == Decimal("-5.00")

    def test_zero_value(self) -> None:
        acct = make_account(CENT_ACCOUNT_FACTOR)
        result = acct.normalize_to_usd(Decimal("0"))
        assert result == Decimal("0.00")

    def test_matches_canonical_service_for_various_inputs(self) -> None:
        """Parametric regression: model output must always match service output."""
        factor = CENT_ACCOUNT_FACTOR
        acct = make_account(factor)
        for raw in ("1", "100", "9999", "12345.6789", "-250"):
            broker_val = Decimal(raw)
            assert acct.normalize_to_usd(broker_val) == normalize_broker_to_usd(
                broker_val, factor
            ), f"Mismatch for input {raw!r}"

    def test_rounding_half_even(self) -> None:
        """
        Canonical service uses ROUND_HALF_EVEN.
        Model method must use the same rounding via delegation.
        """
        # Construct a value where rounding matters
        # 0.005 with ROUND_HALF_EVEN rounds to 0.00 (even) not 0.01
        # Use factor=1 (standard account) and broker value with fractional cents
        acct = make_account(STANDARD_USD_FACTOR)
        result = acct.normalize_to_usd(Decimal("1.005"))
        expected = normalize_broker_to_usd(Decimal("1.005"), STANDARD_USD_FACTOR)
        assert result == expected  # Both must agree on rounding direction
