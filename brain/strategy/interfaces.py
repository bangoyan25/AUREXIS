"""
Strategy interfaces for the AUREXIS Brain.

These are the structural contracts that trading strategy components must implement.
Final strategy formulas (indicator parameters, entry/exit rules, signal scoring,
market structure/breakout/fakeout definitions) are UNDEFINED.

Components return NOT_CONFIGURED when required configuration is absent.
No trading strategy logic is invented here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any


class StrategyStatus(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"   # Required parameters missing
    CONFIGURED = "CONFIGURED"           # Ready to analyze
    ANALYZING = "ANALYZING"             # Processing in progress


class SignalDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"   # No signal — neutral market condition


@dataclass(frozen=True)
class CandidateSignal:
    """
    Output of the strategy engine — a potential trade to be evaluated by Risk Engine.

    This is NOT an order. It becomes a command only if the Risk Engine approves.
    direction == NONE means no trade recommendation.
    """
    symbol: str
    direction: SignalDirection
    # Confidence score — UNDEFINED until signal scoring formula is approved
    # None means not configured. Downstream must handle None.
    confidence_score: Decimal | None
    # SL/TP levels — UNDEFINED until formula is approved
    suggested_stop_loss: Decimal | None
    suggested_take_profit: Decimal | None
    # Strategy metadata for audit trail
    strategy_id: str
    strategy_version: str
    market_state_summary: str
    is_configured: bool   # False if strategy params are UNDEFINED
    entry_reference: Decimal | None = None
    correlation_id: str | None = None
    expires_at: Any = None
    evidence: dict[str, Any] = None  # type: ignore[assignment]
    setup_type: str | None = None



class MarketStructureAnalyzer(ABC):
    """
    Identifies market structure (higher highs, lower lows, ranges).
    Final definition UNDEFINED — implement interface, not formula.
    """

    @abstractmethod
    def analyze(self, symbol: str) -> dict[str, Any]:
        """Return current market structure assessment. UNDEFINED formula."""
        ...

    @property
    @abstractmethod
    def status(self) -> StrategyStatus:
        ...


class TrendAnalyzer(ABC):
    """
    Determines trend direction and strength.
    Final indicators and thresholds UNDEFINED.
    """

    @abstractmethod
    def analyze(self, symbol: str) -> dict[str, Any]:
        ...

    @property
    @abstractmethod
    def status(self) -> StrategyStatus:
        ...


class BreakoutAnalyzer(ABC):
    """
    Detects breakout conditions.
    Breakout definition UNDEFINED — implement interface, not formula.
    """

    @abstractmethod
    def analyze(self, symbol: str) -> dict[str, Any]:
        ...

    @property
    @abstractmethod
    def status(self) -> StrategyStatus:
        ...


class FakeoutAnalyzer(ABC):
    """
    Detects fakeout/false breakout conditions.
    Fakeout definition UNDEFINED — implement interface, not formula.
    """

    @abstractmethod
    def analyze(self, symbol: str) -> dict[str, Any]:
        ...

    @property
    @abstractmethod
    def status(self) -> StrategyStatus:
        ...


class SignalScorer(ABC):
    """
    Combines analysis outputs into a signal confidence score.
    Scoring formula UNDEFINED.
    """

    @abstractmethod
    def score(self, analyses: dict[str, Any]) -> Decimal | None:
        """Return confidence score, or None if not configured."""
        ...

    @property
    @abstractmethod
    def status(self) -> StrategyStatus:
        ...


class StrategyEngine(ABC):
    """
    Top-level orchestrator that runs all analyzers and produces a CandidateSignal.

    Returns CandidateSignal with is_configured=False and direction=NONE
    when any required component is NOT_CONFIGURED.
    """

    @abstractmethod
    def generate_signal(self, symbol: str) -> CandidateSignal:
        """
        Generate a trading signal candidate.
        Returns a NONE signal if any required component is NOT_CONFIGURED.
        """
        ...

    @property
    @abstractmethod
    def status(self) -> StrategyStatus:
        ...


class NotConfiguredStrategyEngine(StrategyEngine):
    """
    Placeholder strategy engine that returns NOT_CONFIGURED.

    Used until the final strategy specification is approved and implemented.
    This is the only strategy engine active during Phase 1/2.
    It never generates live signals.
    """

    def generate_signal(self, symbol: str) -> CandidateSignal:
        return CandidateSignal(
            symbol=symbol,
            direction=SignalDirection.NONE,
            confidence_score=None,
            suggested_stop_loss=None,
            suggested_take_profit=None,
            strategy_id="NOT_CONFIGURED",
            # "0.0.0" denotes the not-configured state — not a production version.
            # When a real strategy is implemented, this will come from its own versioned module.
            strategy_version="0.0.0-not-configured",
            market_state_summary=(
                "Strategy parameters (indicators, entry/exit rules, signal scoring, "
                "market structure/breakout/fakeout definitions) are UNDEFINED. "
                "Awaiting formal specification approval."
            ),
            is_configured=False,
        )

    @property
    def status(self) -> StrategyStatus:
        return StrategyStatus.NOT_CONFIGURED
