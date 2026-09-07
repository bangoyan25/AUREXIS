# AUREXIS Market Structure Specification

> **Status:** DRAFT — 2026-09-06
> **Authority:** `docs/MASTER_SPECIFICATION.md` v1.0 (LOCKED)
> **No production parameters defined. All thresholds: UNDEFINED.**

---

## 1. Purpose

Market structure is the primary framework for reading XAUUSD price behavior.
It is non-indicator and event-based. All other analysis layers are anchored to it.

---

## 2. Swing Detection (Mathematical)

### 2.1 Definitions

Let `H[i]` = high of bar i, `L[i]` = low of bar i.

**Swing High at bar i:**
```
is_swing_high(i) = True iff:
    H[i] > H[j] for all j in [i-N .. i-1]   (N bars before)
    AND
    H[i] > H[j] for all j in [i+1 .. i+N]   (N bars after)
```

**Swing Low at bar i:**
```
is_swing_low(i) = True iff:
    L[i] < L[j] for all j in [i-N .. i-1]
    AND
    L[i] < L[j] for all j in [i+1 .. i+N]
```

**N (swing lookback period):** UNDEFINED — requires approval.

### 2.2 Look-Ahead Bias Prevention (Absolute Rule)

Confirmation of bar i as a swing requires bars i+1 through i+N to have closed.
The most recent confirmed swing is always at least N bars old.

**Implementation rule:** Never mark a bar as a swing until N future bars have closed.
The current (open) bar is never a swing candidate.
No exception.

### 2.3 Tie-Breaking

If H[i] == H[i+1]: do NOT classify as swing high (conservative default).
Tie-breaking rule: CONFIGURABLE — UNDEFINED.

---

## 3. Pattern Classification

Let:
- SH₁ = most recent confirmed swing high | SH₀ = previous confirmed swing high
- SL₁ = most recent confirmed swing low  | SL₀ = previous confirmed swing low

| Pattern | Condition |
|---------|-----------|
| Higher High (HH) | SH₁ > SH₀ |
| Higher Low (HL) | SL₁ > SL₀ |
| Lower High (LH) | SH₁ < SH₀ |
| Lower Low (LL) | SL₁ < SL₀ |
| Equal High/Low | abs(level₁ - level₀) <= EQ_TOLERANCE (UNDEFINED) |

### Structural States

| State | Condition |
|-------|-----------|
| `BULLISH` | HH + HL confirmed (minimum pair count: UNDEFINED) |
| `BEARISH` | LH + LL confirmed (minimum pair count: UNDEFINED) |
| `RANGING` | Neither consistent progression |
| `BROKEN_UP` | BOS_UP just confirmed |
| `BROKEN_DOWN` | BOS_DOWN just confirmed |
| `INSUFFICIENT_DATA` | Below minimum confirmed swings |

---

## 4. Break of Structure (BOS)

**BOS_UP at bar i:**
```
close[i] > SH₁  AND  (close[i] - SH₁) >= MIN_BOS_DISTANCE
```

**BOS_DOWN at bar i:**
```
close[i] < SL₁  AND  (SL₁ - close[i]) >= MIN_BOS_DISTANCE
```

MIN_BOS_DISTANCE: UNDEFINED (prevents micro-violation noise).

Rules:
- Only confirmed closed bar closes count — NEVER open bar
- Wick-only pierce does NOT constitute BOS
- If within MIN_BOS_DISTANCE: log `near_bos_level` event, state unchanged

---

## 5. Change of Character (CHoCH)

First BOS counter to prevailing structural state.

In `BULLISH`: first BOS_DOWN (close below most recent HL) = CHoCH.
In `BEARISH`: first BOS_UP (close above most recent LH) = CHoCH.

Effect: structure → `BROKEN_DOWN` or `BROKEN_UP`; regime → `TRANSITION`.
Not a trade entry by itself.

---

## 6. Multi-Timeframe Structure

Structure computed independently on HTF and MTF. They may disagree.

| HTF | MTF | Signal Eligibility |
|-----|-----|--------------------|
| `BULLISH` | `BULLISH` or `BROKEN_UP` | BUY setups eligible |
| `BEARISH` | `BEARISH` or `BROKEN_DOWN` | SELL setups eligible |
| Mismatch | Any | NO signal |
| Any | `INSUFFICIENT_DATA` | NO signal |
| `INSUFFICIENT_DATA` | Any | NO signal |
| `TRANSITION` on HTF | Any | NO signal |

---

## 7. Reference Level Management

Level validity: CONFIGURABLE maximum bar age — UNDEFINED.
Expired levels discarded and not used as breakout references.

Level reclaim: After BOS_DOWN, close back above broken level on confirmed bar → potential BULLISH_FAKEOUT.

---

## 8. Noise Filtering

XAUUSD noise sources: spread expansion wicks; session-open first-bar extremes; news spikes.

Mitigations:
- Use only bar closes for structural decisions
- Minimum BOS distance filter (UNDEFINED)
- Swing N parameter (UNDEFINED)

Do not hardcode any noise filter without empirical XAUUSD calibration.

---

## 9. Insufficient Data Behavior

Startup / reconnect: structural state = `INSUFFICIENT_DATA` until minimum swing pairs confirmed (UNDEFINED).
`INSUFFICIENT_DATA` → NO candidate signals.
Historical bars minimum lookback: CONFIGURABLE — UNDEFINED.

---

## 10. Look-Ahead Bias Checklist

Before any implementation:
- [ ] Swing confirmation never uses unclosed bar
- [ ] BOS detection never uses unclosed bar
- [ ] Pattern classification never uses unclosed bar
- [ ] Reference level never uses unclosed bar
- [ ] No structure code reads `close[i]` for currently-open bar
- [ ] Tests include swing appearing to form but not yet N-bar confirmed
- [ ] Tests include N future bars failing to confirm the swing
