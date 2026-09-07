"""
Cent account normalization utilities.

Explicit, tested functions for converting broker-native monetary units to USD.

Cent account rule: broker reports value in cents.
  10,000 broker cents = $100.00 USD

IMPORTANT:
- Always use Decimal for monetary arithmetic — never float.
- The normalization factor must be stored per-account in the database.
- Never assume a global cent factor applies to all accounts.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation


class MonetaryNormalizationError(Exception):
    """Raised when monetary normalization cannot be completed safely."""
    pass


def normalize_broker_to_usd(
    broker_value: Decimal,
    cent_normalization_factor: Decimal,
) -> Decimal:
    """
    Convert a broker-native monetary value to USD using the account's factor.

    Args:
        broker_value: Value as reported by the broker (may be in cents)
        cent_normalization_factor: Stored per-account factor.
            1.0 for standard USD accounts.
            0.01 for Cent accounts (10000 cents = $100).

    Returns:
        USD value as Decimal, rounded to 2 decimal places.

    Raises:
        MonetaryNormalizationError: if inputs are invalid.
    """
    if cent_normalization_factor <= Decimal("0"):
        raise MonetaryNormalizationError(
            f"cent_normalization_factor must be positive, got {cent_normalization_factor!r}"
        )
    try:
        usd = broker_value * cent_normalization_factor
        return usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    except InvalidOperation as exc:
        raise MonetaryNormalizationError(
            f"Cannot normalize {broker_value!r} with factor {cent_normalization_factor!r}"
        ) from exc


def usd_to_broker(
    usd_value: Decimal,
    cent_normalization_factor: Decimal,
) -> Decimal:
    """
    Convert a USD value back to broker-native units.

    Inverse of normalize_broker_to_usd.
    Used when constructing order volumes for the MT5 EA.
    """
    if cent_normalization_factor <= Decimal("0"):
        raise MonetaryNormalizationError(
            f"cent_normalization_factor must be positive, got {cent_normalization_factor!r}"
        )
    return usd_value / cent_normalization_factor


# Standard factors — for reference and testing only.
# Production factor is always read from the TradingAccount record.
CENT_ACCOUNT_FACTOR = Decimal("0.01")
STANDARD_USD_FACTOR = Decimal("1.0")
