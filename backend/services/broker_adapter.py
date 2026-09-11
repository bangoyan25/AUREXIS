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
            "HFMarketGlobal-Demo4",
            "HFMarketsGlobal-Demo",
            "HFMarketsGlobal-Demo2",
            "HFMarketsGlobal-Demo3",
            "HFMarketsGlobal-Live",
            "HFMarketsGlobal-Live2",
            "HFMarketsGlobal-Live3",
            "HFMarketsSV-Live",
            "HFMarketsSV-Live2",
            "HFMarketsSV-Live3",
            "HFMarketsSV-Live4",
            "HFMarketsSV-Live5",
            "HFMarketsSV-Live6",
            "HFMarketsSV-Live7",
            "HFMarketsSV-Demo",
            "HFMarketsSA-Live",
            "HFMarketsSA-Demo",
            "HFMarketsEurope-Live",
            "HFMarketsEurope-Demo",
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
            "Exness-Real6",
            "Exness-Real7",
            "Exness-Real8",
            "Exness-Real9",
            "Exness-Real10",
            "Exness-Real11",
            "Exness-Real12",
            "Exness-Real13",
            "Exness-Real14",
            "Exness-Real15",
            "Exness-Real16",
            "Exness-Real17",
            "Exness-Real18",
            "Exness-Real19",
            "Exness-Real20",
            "Exness-Real21",
            "Exness-Real22",
            "Exness-Real23",
            "Exness-Real24",
            "Exness-Real25",
            "Exness-Real26",
            "Exness-Real27",
            "Exness-Real28",
            "Exness-Real29",
            "Exness-Real30",
            "Exness-Real31",
            "Exness-Real32",
            "Exness-Real33",
            "Exness-Real34",
            "Exness-Real35",
            "Exness-Real36",
            "Exness-Trial",
            "Exness-Trial2",
            "Exness-Trial3",
            "Exness-Trial4",
            "Exness-Trial5",
            "Exness-Trial6",
            "Exness-Trial7",
            "Exness-Trial8",
            "Exness-Trial9",
            "Exness-Trial10",
        ],
        supports_cent_accounts=True,
        cent_suffix="c",
    )


_BROKERS: dict[str, type[BaseBrokerAdapter]] = {
    "HFM": HFMBrokerAdapter,
    "Exness": ExnessBrokerAdapter,
}

_HFM_ALIASES = {
    "HFM",
    "HF MARKETS",
    "HFMARKETS",
    "HF MARKET",
    "HF MARKET (SV) LTD",
    "HF MARKET (SV) LTD.",
    "HF MARKETS (SV) LTD",
    "HF MARKETS (SV) LTD.",
    "HF MARKETS GLOBAL",
    "HF MARKETS SV",
    "HFM INVESTMENTS",
    "HFM INVESTMENTS LTD",
    "HF MARKETS EUROPE LTD",
}

_EXNESS_ALIASES = {
    "EXNESS",
    "EXNESS LLC",
    "EXNESS (SC) LTD",
    "EXNESS (SC) LTD.",
    "EXNESS TECHNOLOGIES",
    "EXNESS TECHNOLOGIES LTD",
    "EXNESS B.V.",
    "EXNESS GLOBAL",
}


def normalize_broker_name(raw_broker: str) -> str:
    """Normalize and validate broker name against supported brokers (HFM, Exness)."""
    clean = " ".join(raw_broker.strip().upper().split())
    if clean in _HFM_ALIASES or any(clean.startswith(a) for a in ("HFM", "HF MARKET", "HFMARKET")):
        return "HFM"
    if clean in _EXNESS_ALIASES or clean.startswith("EXNESS"):
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
            "default_symbol": HFMBrokerAdapter.metadata.default_gold_symbol,
            "currencies": ["USD", "EUR", "GBP", "IDR", "USDCent"],
        },
        {
            "id": "Exness",
            "name": ExnessBrokerAdapter.metadata.display_name,
            "servers": ExnessBrokerAdapter.metadata.known_servers,
            "supports_cent": ExnessBrokerAdapter.metadata.supports_cent_accounts,
            "default_symbol": ExnessBrokerAdapter.metadata.default_gold_symbol,
            "currencies": ["USD", "EUR", "GBP", "IDR", "USDCent"],
        },
    ]
