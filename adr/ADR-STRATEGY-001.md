# ADR-STRATEGY-001: Centralized Strategy Configuration, 6-Dimension Evidence Assembly, and Fail-Closed Architecture

## Status
ACCEPTED — 2026-09-06

## Context
AUREXIS requires a deterministic, testable, and locally backtestable Brain engine for XAUUSD trading.
Prior to TASK-003, strategy interfaces existed but all empirical thresholds were UNDEFINED.
A principled quantitative architecture was needed to avoid indicator stacking, look-ahead bias, and overfitting.

## Decision

1. **Centralized Configuration (`BrainConfig`)**:
   All empirical parameters (lookbacks, thresholds, weights, R:R targets, protection limits) live in a single canonical configuration object in `brain/config.py`. No magic constants are scattered across modules.

2. **Strategy Versioning**:
   Every `CandidateSignal` carries `strategy_version: "AUREXIS-STRAT-1.0.0"`. Any parameter or formula modification requires bumping this version to preserve full auditability.

3. **6 Independent Evidence Dimensions**:
   - Structure (25%): Swing pivots, BOS with min ATR displacement, CHoCH.
   - Setup (25%): Closed-bar breakout or fakeout reversal confirmation.
   - Trend (20%): EMA alignment + Wilder ADX trend strength.
   - Momentum (10%): Wilder RSI with overbought/oversold exhaustion zones.
   - Volatility (10%): Normalized ATR ratio against rolling baseline.
   - Regime (10%): Macro-regime alignment with anti-flapping hysteresis.
   Total = 100%. Minimum confidence = 0.70.

4. **Hard Gates Precedence**:
   Hard gates (market data not ready, stale tick, wide spread, news blackout, unsafe regime) are evaluated **before** scoring. High confidence cannot override a hard block.

5. **Closed-Bar Invariant**:
   All indicators and structural calculations operate exclusively on closed bars (`is_closed=True`).
   Ticks are used solely for real-time observation (bid/ask, spread check, staleness check).

6. **Generalized Dynamic Profit Lock**:
   Uses floating equity basis: `protected_gain = peak_gain * lock_ratio` with monotonic floor.
   Supercedes old illustrative static examples.

7. **Live Trading Lock**:
   `trading_enabled = False` remains strictly enforced. All components run in LOCAL / SIMULATION mode.

## Consequences
- Strategy is fully explainable and auditable.
- Backtesting and live evaluation share identical Brain and Risk engine code paths.
- No lookahead bias is possible due to closed-bar enforcement.
- Live trading cannot be activated accidentally.
