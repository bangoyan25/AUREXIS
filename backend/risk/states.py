"""
Risk Engine state definitions.

The Risk Engine is a deterministic state machine.
It evaluates candidate signals against account state, market conditions,
and configured risk parameters.

CRITICAL: All production risk thresholds are UNDEFINED.
The Risk Engine will return NOT_CONFIGURED for any required missing parameter.
No trading occurs until all required parameters are formally approved.
"""

from __future__ import annotations

from enum import StrEnum


class RiskState(StrEnum):
    """
    Risk Engine operational states.

    The Risk Engine starts in NOT_CONFIGURED.
    Transitions to NORMAL only when all required parameters are configured.
    Can degrade to CAUTION, PROTECTED, STOPPED, or EMERGENCY_STOP
    based on account conditions.
    """
    NOT_CONFIGURED = "NOT_CONFIGURED"  # Required parameters missing — no trading
    NORMAL = "NORMAL"                  # All checks pass — trading permitted (if signal)
    CAUTION = "CAUTION"                # Approaching limits — trading with extra care
    PROTECTED = "PROTECTED"            # Profit lock active — position management only
    STOPPED = "STOPPED"                # Daily limit hit or drawdown limit hit — no new entries
    EMERGENCY_STOP = "EMERGENCY_STOP"  # Manual override — all trading halted


class SignalDecision(StrEnum):
    """
    Risk Engine decision for a candidate signal.
    """
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    EMERGENCY = "EMERGENCY"


# Allowed trading states — only NORMAL permits new entries
TRADING_ALLOWED_STATES: frozenset[RiskState] = frozenset({RiskState.NORMAL})

# States where position management (SL/TP moves, closes) may still be allowed
POSITION_MANAGEMENT_ALLOWED_STATES: frozenset[RiskState] = frozenset({
    RiskState.NORMAL,
    RiskState.CAUTION,
    RiskState.PROTECTED,
})
