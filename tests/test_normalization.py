"""
Unit tests for cent account normalization.

Critical: financial values must never be mixed with the wrong unit.
These tests verify the normalization layer that separates
broker-native cents from AUREXIS normalized USD values.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.services.normalization import (
    CENT_ACCOUNT_FACTOR,
    STANDARD_USD_FACTOR,
    MonetaryNormalizationError,
    normalize_broker_to_usd,
    usd_to_broker,
)


@pytest.mark.unit
class TestCentAccountNormalization:
    """Test the broker → USD conversion for cent accounts."""

    def test_10000_cents_equals_100_usd(self) -> None:
        """The canonical cent account example from the spec."""
        result = normalize_broker_to_usd(
            broker_value=Decimal("10000"),
            cent_normalization_factor=CENT_ACCOUNT_FACTOR,
        )
        assert result == Decimal("100.00")

    def test_1_cent_equals_001_usd(self) -> None:
        result = normalize_broker_to_usd(
            broker_value=Decimal("1"),
            cent_normalization_factor=CENT_ACCOUNT_FACTOR,
        )
        assert result == Decimal("0.01")

    def test_zero_broker_value(self) -> None:
        result = normalize_broker_to_usd(
            broker_value=Decimal("0"),
            cent_normalization_factor=CENT_ACCOUNT_FACTOR,
        )
        assert result == Decimal("0.00")

    def test_negative_broker_value(self) -> None:
        """Losses are negative — normalization must preserve sign."""
        result = normalize_broker_to_usd(
            broker_value=Decimal("-500"),
            cent_normalization_factor=CENT_ACCOUNT_FACTOR,
        )
        assert result == Decimal("-5.00")

    def test_standard_usd_account_unchanged(self) -> None:
        """Standard USD account: factor 1.0 must not alter the value."""
        result = normalize_broker_to_usd(
            broker_value=Decimal("1234.56"),
            cent_normalization_factor=STANDARD_USD_FACTOR,
        )
        assert result == Decimal("1234.56")

    def test_result_rounded_to_2dp(self) -> None:
        """USD values must be rounded to 2 decimal places."""
        result = normalize_broker_to_usd(
            broker_value=Decimal("3"),
            cent_normalization_factor=Decimal("0.01"),
        )
        assert result == Decimal("0.03")

    def test_zero_factor_raises(self) -> None:
        with pytest.raises(MonetaryNormalizationError):
            normalize_broker_to_usd(
                broker_value=Decimal("100"),
                cent_normalization_factor=Decimal("0"),
            )

    def test_negative_factor_raises(self) -> None:
        with pytest.raises(MonetaryNormalizationError):
            normalize_broker_to_usd(
                broker_value=Decimal("100"),
                cent_normalization_factor=Decimal("-0.01"),
            )


@pytest.mark.unit
class TestUsdToBroker:
    def test_100_usd_to_10000_cents(self) -> None:
        result = usd_to_broker(
            usd_value=Decimal("100"),
            cent_normalization_factor=CENT_ACCOUNT_FACTOR,
        )
        assert result == Decimal("10000")

    def test_standard_account_identity(self) -> None:
        result = usd_to_broker(
            usd_value=Decimal("500.25"),
            cent_normalization_factor=STANDARD_USD_FACTOR,
        )
        assert result == Decimal("500.25")

    def test_round_trip(self) -> None:
        """normalize_broker_to_usd then usd_to_broker must return original value."""
        original = Decimal("5000")
        usd = normalize_broker_to_usd(original, CENT_ACCOUNT_FACTOR)
        back = usd_to_broker(usd, CENT_ACCOUNT_FACTOR)
        assert back == original


@pytest.mark.unit
class TestNormalizationUnitSafety:
    """Verify that float is never used in monetary calculations."""

    def test_inputs_are_decimal_not_float(self) -> None:
        """Function must accept Decimal, not silently coerce float."""
        # Passing a float is a programming error — must work with Decimal
        result = normalize_broker_to_usd(
            broker_value=Decimal("100"),
            cent_normalization_factor=Decimal("0.01"),
        )
        assert isinstance(result, Decimal)
        assert not isinstance(result, float)
