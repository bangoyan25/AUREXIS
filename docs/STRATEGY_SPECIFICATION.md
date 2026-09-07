# AUREXIS Strategy Specification

> **Status:** DRAFT — 2026-09-06
> **Authority:** `docs/MASTER_SPECIFICATION.md` v1.0 (LOCKED)
> **Symbol:** XAUUSD only
> **CRITICAL:** All thresholds, periods, weights needing empirical validation: **UNDEFINED**.

---

## 1. Design Principle: Independent Evidence

Stacking EMA + MACD + Bollinger counts one evidence source three times.
AUREXIS uses six genuinely independent dimensions:

| Dimension | Measures | Independence reason |
|-----------|----------|-------------------|
| Market Regime | Macro context | Coarse classifier; gates setup validity |
| Market Structure | HH/HL/LH/LL, BOS | Non-indicator, structural |
| Trend | Directional bias + strength | Smoothed price |
| Momentum | Rate-of-change, energy | Independent of direction |
| Volatility | ATR-class environment | Direction-independent |
| Breakout Context | Price at/through structure | Event-based, not smoothed |

**Absolute rule:** All bar-level calculations use confirmed closed bars only.
Tick-level = observation and validation, zero predictive calculation.

---

## 2. Market Regime

States: `TREND_UP`, `TREND_DOWN`, `RANGE`, `TRANSITION`, `HIGH_VOLATILITY`, `UNKNOWN`

`UNKNOWN` → NO TRADE always.

Detection on HTF closed bars (HTF period: UNDEFINED).
Evidence: structural progression + smoothed price alignment + trend strength + volatility level.
Weighting: **UNDEFINED**. Anti-flapping: N consecutive bars required (N: UNDEFINED).
Formal state machine: `docs/REGIME_SPECIFICATION.md`.

| Regime | Valid Setups |
|--------|-------------|
| `TREND_UP` | Trend-continuation BUY; Bullish breakout; Bullish fakeout |
| `TREND_DOWN` | Trend-continuation SELL; Bearish breakout; Bearish fakeout |
| `RANGE` | Range setups (UNDEFINED) |
| `TRANSITION`, `HIGH_VOLATILITY`, `UNKNOWN` | None |

---

## 3. Market Structure

### Swing Detection (closed bars only)

Swing high: bar high exceeds N bars before AND N bars after (N: UNDEFINED).
Swing low: bar low below N bars before AND N bars after.
Confirmation delayed N bars — by design, prevents look-ahead bias.

### Patterns

HH: latest swing high > previous swing high.
HL: latest swing low > previous swing low.
LH: latest swing high < previous swing high.
LL: latest swing low < previous swing low.
Equal HH/LL tolerance: UNDEFINED.

### Structural States

`BULLISH` (HH+HL, min count: UNDEFINED) | `BEARISH` (LH+LL) | `RANGING` | `BROKEN_UP` | `BROKEN_DOWN` | `INSUFFICIENT_DATA`

### BOS and CHoCH

BOS: close beyond most recent opposing swing point on confirmed bar.
Min BOS distance: UNDEFINED (prevents micro-violations). Wick-only violations do NOT qualify.
CHoCH: first BOS counter to established trend → `TRANSITION` regime, not a trade entry.

Multi-timeframe: structure computed on HTF and MTF independently.
Both must align. Conflict → NO signal.

---

## 4. Trend

Direction: one smoothed price indicator, MTF closed bars. Class: EMA or equivalent. Period: UNDEFINED.
Strength: one non-directional strength indicator. Class: ADX or equivalent. Period + threshold: UNDEFINED.

ADX = strength, NOT direction. Must be paired with directional evidence.
Max one trend direction + one trend strength indicator. No stacking.

---

## 5. Breakout

Breakout = confirmed close beyond structural reference level. NOT: tick crossing, wick only, marginal close.

Valid reference levels: confirmed swing high/low; range boundary; prior BOS level. Age max: UNDEFINED.

Validity requirements (all required):
closed bar beyond level | close distance > minimum (UNDEFINED) | regime compatible | momentum supportive | volatility not ABNORMAL_HIGH | spread within limit (UNDEFINED) | news CLEAR.

Invalidation: close back inside level; expiry elapsed (UNDEFINED); regime degrades; news event.

---

## 6. Fakeout

Fakeout requires all of: valid breakout occurred first (per §5 — NOT just a wick) + full bar close
back inside level + return has directional momentum (weak return = noise; strong = fakeout).

`BULLISH_FAKEOUT`: failed bearish breakout → BUY candidate.
`BEARISH_FAKEOUT`: failed bullish breakout → SELL candidate.

Reversal momentum threshold: UNDEFINED. Ambiguous oscillation → CANDIDATE_FORMING, no signal.
Second close beyond original level → setup invalidated (breakout was real).

---

## 7. Momentum

Purpose: energy and rate-of-change, independent of trend direction.

Indicator class: RSI-class or ROC-class (selection UNDEFINED, period UNDEFINED).
Usage: momentum context — not a buy/sell threshold trigger.
RSI overbought/sold thresholds not used as entries in trending markets.

Momentum divergence (price new extreme, indicator not): reduces confidence score.
Does not auto-block if score remains above threshold.

Momentum does NOT generate signals alone. Contributes to confidence model.

---

## 8. Volatility

ATR or equivalent. Period: UNDEFINED. Computed on confirmed closed bars only.

States: `NORMAL` | `EXPANDING` | `CONTRACTING` | `ABNORMAL_HIGH` | `ABNORMAL_LOW`
All thresholds: UNDEFINED until XAUUSD-specific calibration complete.

Breakout in EXPANDING: higher genuine likelihood. In CONTRACTING/ABNORMAL_LOW: higher fakeout risk.
In ABNORMAL_HIGH: NO new entry.

XAUUSD characteristics requiring calibration: sharp moves on USD releases (NFP/CPI/FOMC); London > Asian volatility; NY open spike risk; geopolitical sensitivity; spread expansion during illiquid periods; Sunday reopen gaps.

---

## 9. Multi-Timeframe Design

| Role | Purpose | Period |
|------|---------|--------|
| HTF | Macro regime, primary structure, directional context | UNDEFINED |
| MTF | Setup formation, trend context | UNDEFINED |
| Tick Stream | Entry timing, spread, microstructure | Live |

HTF (closed bars only): regime, primary structure, primary trend direction + strength.
MTF (closed bars only): secondary structure, setup detection, trend confirmation.
Tick-level: price/spread observation + proximity to reference level. No closed-bar calculations.

HTF + MTF conflict → NO TRADE.

---

## 10. Conflict Resolution Hierarchy

Priority 1 — Emergency stop / account stop → NO TRADE (absolute).
Priority 2 — Risk Engine REJECTED/BLOCKED → NO TRADE (absolute).
Priority 3 — News non-CLEAR → NO TRADE.
Priority 4 — Market state not READY → NO TRADE.
Priority 5 — Regime UNKNOWN / HIGH_VOLATILITY → NO TRADE.
Priority 6 — HTF vs MTF structure misalignment → NO TRADE.
Priority 7 — Trend vs Structure conflict → NO TRADE.
Priority 8 — Confidence below threshold → NO TRADE.
Priority 9 — Momentum neutral → reduce confidence (may trade if score sufficient).
Priority 10 — Structure weak, momentum ok → reduce confidence (may trade if score sufficient).

Priorities 1–8: hard block. Priorities 9–10: soft confidence reduction.

---

## 11. Entry / Exit Model

### Entry
Setup detected (regime+structure+trend+breakout/fakeout align) → CANDIDATE_FORMING.
Confirmation: spread within limit (UNDEFINED) + no adverse jump + news CLEAR.
Signal validity window: UNDEFINED. One signal per account in PENDING_RISK at a time.

### Stop Loss
At structurally meaningful invalidation reference. ATR buffer multiplier: UNDEFINED. Algorithm: UNDEFINED.

### Take Profit
Next structural reference in trade direction. Algorithm: UNDEFINED. R:R minimum: UNDEFINED.

### Break-Even and Trailing
Break-even distance threshold: UNDEFINED. Trailing formula: UNDEFINED.

### Exit Hierarchy
```
Emergency exit (Risk Engine kill)   → unconditional override
Risk exit (daily limit / drawdown)  → overrides strategy exits
Invalidation exit (setup broken)    → overrides TP/SL
Strategy stop loss                  → explicit SL
Take profit                         → explicit TP
Break-even / trail                  → dynamic SL
```

---

## 12. News Protection

States: CLEAR | PRE_EVENT | IN_EVENT | POST_EVENT | UNKNOWN | PROVIDER_UNAVAILABLE | STALE.
Non-CLEAR → NO new entry. UNKNOWN/UNAVAILABLE/STALE → treat as PRE_EVENT (conservative fail-safe).
Pre/post windows: UNDEFINED. Provider, event selection: UNDEFINED.
Existing position behavior during news: UNDEFINED (separate specification required).

---

## 13. Position Sizing Interface

Brain provides: `suggested_stop_loss` + `suggested_take_profit` (price levels).
Risk Engine / Sizing module computes lot size from equity, risk % (UNDEFINED), stop distance,
symbol contract spec, broker constraints, max exposure (UNDEFINED).
Production sizing formula: UNDEFINED.

---

## 14. Overfitting Protection

| Risk | Mitigation |
|------|-----------|
| Indicator stacking | Six independent dimensions; one indicator per dimension max |
| Parameter overfitting | All params UNDEFINED until empirical approval |
| Look-ahead bias | Bar-close-only; tick = observation only |
| Survivorship bias | Backtest includes losing periods and data gaps |
| Curve fitting | Walk-forward validation required |
| Spread blindness | Spread validation required at signal generation |
| Slippage blindness | Backtest uses realistic bid/ask, not mid-price fills |

---

## Appendix A — UNDEFINED Parameters (Master List)

Timeframes: HTF period, MTF period.
Regime: trend strength threshold; volatility thresholds; anti-flapping N bars.
Structure: swing lookback N; min BOS distance; min swing count; equal HH/HL tolerance.
Trend: EMA period(s); ADX period; ADX trending threshold; consistency window/ratio.
Momentum: indicator selection; period; divergence lookback.
Volatility: ATR period; normal baseline; all state thresholds.
Breakout/Fakeout: min close distance; level age max; signal expiry; reversal momentum threshold.
Scoring: dimension weights; minimum confidence threshold.
Spread: maximum acceptable spread.
Staleness: maximum tick age before STALE.
Entry/Exit: SL/TP algorithm; ATR multiplier; R:R minimum; break-even distance; trailing formula.
Position sizing: risk % per trade; ATR multiplier; max lot size; max basket exposure.
News: provider; pre-event window; post-event window; impact threshold; open position behavior.

