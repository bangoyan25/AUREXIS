"""Broker adapter service for AUREXIS.

Supported brokers:
- HFM (HF Markets)
- Exness
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar


class UnsupportedBrokerError(ValueError):
    """Raised when an unrecognized or unsupported broker is specified."""


@dataclass(frozen=True)
class BrokerMetadata:
    name: str
    display_name: str
    supported_symbols: list[str]
    default_gold_symbol: str
    known_servers: list[str]
    supports_cent_accounts: bool
    cent_suffix: str | None


class BaseBrokerAdapter:
    name: ClassVar[str]
    metadata: ClassVar[BrokerMetadata]

    @classmethod
    def normalize_symbol(cls, symbol: str, is_cent: bool = False) -> str:
        sym = symbol.strip().upper()
        if sym in ("XAUUSD", "GOLD"):
            if is_cent and cls.metadata.cent_suffix:
                return f"XAUUSD{cls.metadata.cent_suffix}"
            return cls.metadata.default_gold_symbol
        return sym

    @classmethod
    def get_cent_factor(cls, is_cent: bool) -> Decimal:
        return Decimal("0.01") if is_cent else Decimal("1.0")


class HFMBrokerAdapter(BaseBrokerAdapter):
    name = "HFM"
    metadata = BrokerMetadata(
        name="HFM",
        display_name="HFM (HF Markets)",
        supported_symbols=["XAUUSD", "XAUUSD.m", "GOLD"],
        default_gold_symbol="XAUUSD",
        known_servers=[
            "HFMarketsSV-Live",
            "HFMarketsSV-Live2",
            "HFMarketsSV-Live3",
            "HFMarketsSV-Demo",
            "HFM-Live",
            "HFM-Demo",
        ],
        supports_cent_accounts=True,
        cent_suffix=".m",
    )


class ExnessBrokerAdapter(BaseBrokerAdapter):
    name = "Exness"
    metadata = BrokerMetadata(
        name="Exness",
        display_name="Exness",
        supported_symbols=["XAUUSD", "XAUUSDm", "XAUUSDc", "XAUUSDk"],
        default_gold_symbol="XAUUSDm",
        known_servers=[
            "Exness-Real",
            "Exness-Real2",
            "Exness-Real3",
            "Exness-Real4",
            "Exness-Real5",
            "Exness-Real10",
            "Exness-Trial",
            "Exness-Trial2",
        ],
        supports_cent_accounts=True,
        cent_suffix="c",
    )


_BROKERS: dict[str, type[BaseBrokerAdapter]] = {
    "HFM": HFMBrokerAdapter,
    "Exness": ExnessBrokerAdapter,
}


def normalize_broker_name(raw_broker: str) -> str:
    """Normalize and validate broker name against supported brokers (HFM, Exness)."""
    key = raw_broker.strip().upper()
    if key in ("HFM", "HF MARKETS", "HFMARKETS"):
        return "HFM"
    if key in ("EXNESS", "EXNESS LLC"):
        return "Exness"
    raise UnsupportedBrokerError(
        f"Unsupported broker: '{raw_broker}'. Supported brokers are HFM and Exness."
    )


def get_broker_adapter(raw_broker: str) -> type[BaseBrokerAdapter]:
    normalized = normalize_broker_name(raw_broker)
    return _BROKERS[normalized]


def get_supported_brokers() -> list[dict[str, object]]:
    return [
        {
            "id": "HFM",
            "name": HFMBrokerAdapter.metadata.display_name,
            "servers": HFMBrokerAdapter.metadata.known_servers,
            "supports_cent": HFMBrokerAdapter.metadata.supports_cent_accounts,
        },
        {
            "id": "Exness",
            "name": ExnessBrokerAdapter.metadata.display_name,
            "servers": ExnessBrokerAdapter.metadata.known_servers,
            "supports_cent": ExnessBrokerAdapter.metadata.supports_cent_accounts,
        },
    ]
