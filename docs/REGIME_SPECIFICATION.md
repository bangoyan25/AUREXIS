# AUREXIS Regime Specification

> **Status:** DRAFT — 2026-09-06
> **Authority:** `docs/MASTER_SPECIFICATION.md` v1.0 (LOCKED)
> **All thresholds requiring empirical validation: UNDEFINED.**

---

## 1. Regime States

| State | Meaning |
|-------|---------|
| `TREND_UP` | Consistent HH+HL; positive momentum |
| `TREND_DOWN` | Consistent LH+LL; negative momentum |
| `RANGE` | Oscillation within S/R; no structural progression |
| `TRANSITION` | Recent CHoCH/BOS; insufficient evidence for new regime |
| `HIGH_VOLATILITY` | ATR significantly above norm (threshold: UNDEFINED) |
| `UNKNOWN` | Insufficient data; warm-up; contradiction |

---

## 2. State Machine Transitions

| From | To | Trigger |
|------|----|---------|
| `UNKNOWN` | `TREND_UP` | Min history + HH+HL + momentum + strength confirmed |
| `UNKNOWN` | `TREND_DOWN` | Min history + LH+LL + momentum + strength confirmed |
| `UNKNOWN` | `RANGE` | Min history + oscillation evidence |
| `TREND_UP` | `TRANSITION` | CHoCH (BOS_DOWN in bullish structure) |
| `TREND_DOWN` | `TRANSITION` | CHoCH (BOS_UP in bearish structure) |
| `RANGE` | `TRANSITION` | Clear BOS with momentum |
| `TRANSITION` | `TREND_UP` | New HH+HL + momentum + strength (N bars sustained — N: UNDEFINED) |
| `TRANSITION` | `TREND_DOWN` | New LH+LL + momentum + strength (N bars sustained — N: UNDEFINED) |
| `TRANSITION` | `RANGE` | No new structural progression; oscillation |
| `TRANSITION` | `UNKNOWN` | Contradicting evidence persists beyond timeout |
| Any | `HIGH_VOLATILITY` | ATR > ABNORMAL_HIGH threshold (UNDEFINED) |
| `HIGH_VOLATILITY` | Previous or `UNKNOWN` | ATR normalizes |
| Any | `UNKNOWN` | Data loss / warm-up restart |

---

## 3. Anti-Flapping (Hysteresis)

Problem: a classifier reacting to every bar oscillates on normal retracements.

Solution: transition candidate requires **N consecutive bars** of confirming evidence (N: UNDEFINED).
If evidence breaks before N bars: revert to previous regime or `TRANSITION`.

```
Evidence for new regime detected
    → internal "transition pending" (not exposed externally)
    → count confirming bars
    → N bars confirmed: commit → emit regime_changed event
    → evidence breaks before N: revert
```

N may differ by transition type (all UNDEFINED):
- TREND → TRANSITION; TRANSITION → new TREND; Any → HIGH_VOLATILITY; HIGH_VOLATILITY → other.

HIGH_VOLATILITY may have N=1 (immediate) — volatility is time-critical.
This is a design consideration, not a locked decision.

---

## 4. Evidence Inputs (HTF Closed Bars Only)

| Input | Source | Threshold |
|-------|--------|-----------|
| Structural progression | `MARKET_STRUCTURE_SPEC.md` | Min swing pairs: UNDEFINED |
| Directional smoothed price | Trend indicator (CONFIGURABLE) | UNDEFINED boundary |
| Trend strength | Strength indicator (CONFIGURABLE) | UNDEFINED threshold |
| Volatility level | ATR-class (CONFIGURABLE) | UNDEFINED normal/abnormal |

All inputs: confirmed closed HTF bars only. No open-bar reads.

---

## 5. UNKNOWN State

Triggers:
- Fewer confirmed swings than minimum (UNDEFINED)
- Indicator below warm-up bar count
- Complete contradiction between structure and trend evidence
- Data gap / reconnect

`UNKNOWN` → NO candidate signal, unconditionally.

---

## 6. HIGH_VOLATILITY

Triggered: ATR > ABNORMAL_HIGH (UNDEFINED).
Effect: NO new candidate signals. Overrides all other regime considerations.
Existing position behavior during HIGH_VOLATILITY: UNDEFINED (separate spec required).

---

## 7. Session Context

Session (Asian/London/NY) is attached as metadata label to market state for observability.
Session-specific regime rules are NOT hardcoded. All session logic: CONFIGURABLE — UNDEFINED.

Regime is suspended on weekend close: state → `UNKNOWN` until sufficient post-reopen bars.

---

## 8. Confidence

Regime classifier optionally emits confidence alongside state.
Low confidence does not block a signal by itself — it reduces overall candidate signal score.
Confidence scoring model: UNDEFINED.

---

## 9. Observable Events

| Event | Trigger |
|-------|---------|
| `brain.regime_changed` | Committed transition |
| `brain.regime_transition_pending` | Hysteresis countdown started |
| `brain.regime_transition_cancelled` | Evidence failed before N bars |
| `brain.regime_high_volatility_entered` | ABNORMAL_HIGH detected |
| `brain.regime_high_volatility_exited` | ATR normalized |
| `brain.regime_unknown` | Insufficient data / contradiction |

---

## 10. Regime → Signal Eligibility

| Regime | New Entry |
|--------|-----------|
| `TREND_UP` | Compatible BUY setups |
| `TREND_DOWN` | Compatible SELL setups |
| `RANGE` | Only if range setups configured (UNDEFINED) |
| `TRANSITION` | Blocked |
| `HIGH_VOLATILITY` | Blocked |
| `UNKNOWN` | Blocked |
