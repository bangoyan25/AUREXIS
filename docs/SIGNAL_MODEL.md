# AUREXIS Signal Model

> **Status:** DRAFT — 2026-09-06
> **Authority:** `docs/MASTER_SPECIFICATION.md` v1.0 (LOCKED)
> **Scoring formula and confidence weights: UNDEFINED.**

---

## 1. Signal vs Order

A **CandidateSignal** is NOT an order. It is a recommendation with evidence.
It becomes an order only if Risk Engine approves AND Execution Engine dispatches it.
`direction=NONE` means NO TRADE.

---

## 2. CandidateSignal Fields

Compatible with `brain/strategy/interfaces.py` and `contracts/signal.schema.json`.

| Field | Type | Description |
|-------|------|-------------|
| `signal_id` | UUID | Unique per signal |
| `account_id` | UUID | Account scope |
| `symbol` | str | Always `XAUUSD` |
| `direction` | enum | `BUY`, `SELL`, `NONE` |
| `timestamp` | datetime UTC | Generation time |
| `expires_at` | datetime UTC | Validity deadline (period: UNDEFINED) |
| `regime` | enum | Regime at signal time |
| `structure_state_htf` | enum | HTF structural state |
| `structure_state_mtf` | enum | MTF structural state |
| `setup_type` | enum | `TREND_CONTINUATION` / `BREAKOUT` / `BULLISH_FAKEOUT` / `BEARISH_FAKEOUT` |
| `entry_reference` | Decimal | Price where entry is valid |
| `invalidation_reference` | Decimal | Price where setup is broken |
| `suggested_stop_loss` | Decimal or None | SL level (algorithm: UNDEFINED) |
| `suggested_take_profit` | Decimal or None | TP level (algorithm: UNDEFINED) |
| `confidence_score` | Decimal [0,1] or None | Aggregate confidence (formula: UNDEFINED) |
| `evidence` | EvidenceRecord | Full provenance |
| `strategy_id` | str | Strategy module |
| `strategy_version` | str | Version string |
| `status` | enum | Lifecycle state |
| `correlation_id` | UUID | Cross-system tracing |

---

## 3. Evidence Record

| Field | Description |
|-------|-------------|
| `regime` | Regime label |
| `regime_confidence` | Classifier confidence (UNDEFINED) |
| `htf_structure`, `mtf_structure` | Structural states |
| `structure_aligned` | bool — HTF and MTF agree |
| `trend_direction` | `BULLISH`, `BEARISH`, `NEUTRAL` |
| `trend_strength` | `STRONG`, `MODERATE`, `WEAK`, `FLAT` (thresholds: UNDEFINED) |
| `trend_aligned` | bool — trend agrees with setup direction |
| `momentum_state` | `SUPPORTING`, `NEUTRAL`, `DIVERGING` |
| `volatility_state` | `NORMAL`, `EXPANDING`, `CONTRACTING`, `ABNORMAL_HIGH`, `ABNORMAL_LOW` |
| `breakout_confirmed` | bool |
| `spread_at_signal` | Decimal |
| `spread_acceptable` | bool (threshold: UNDEFINED) |
| `news_state` | News Engine state at signal time |
| `rejection_reasons` | list[str] — negative factors |
| `supporting_factors` | list[str] — positive factors |

---

## 4. Confidence / Scoring Model

Simple point-sum (EMA=20 + RSI=20 = TRADE) creates false precision from correlated inputs.

Confidence = multi-dimensional evidence quality assessment:
```
confidence = f(regime_compatibility, structure_alignment, trend_alignment,
               momentum_quality, volatility_suitability, breakout_quality,
               spread_acceptability)
```

f() is NOT a simple weighted sum. Requires empirical analysis + approval.
**Formula: UNDEFINED.**

Hard blocks (unconditional — no score computation needed):
- Regime incompatible with setup
- HTF + MTF structure misaligned
- Volatility ABNORMAL_HIGH
- Spread not acceptable
- News non-CLEAR

Soft contributions (to confidence score; weights: UNDEFINED):
- Trend aligned + strong: positive
- Trend aligned + weak: smaller positive
- Momentum supporting: positive
- Momentum diverging: negative
- Volatility NORMAL/EXPANDING: suitable for breakout
- Volatility CONTRACTING: neutral / slightly negative

Minimum confidence threshold to forward signal: **UNDEFINED**.

---

## 5. Signal Lifecycle

```
CANDIDATE_FORMING → CANDIDATE_READY → NEWS_BLOCKED ⇄ CANDIDATE_READY
                                    → PENDING_RISK
                                        → RISK_APPROVED → FORWARDED (terminal)
                                        → RISK_REJECTED (terminal)
                                    → EXPIRED (terminal)
                                    → INVALIDATED (terminal)
```

One signal per account in PENDING_RISK at a time.
No new setup while existing is PENDING_RISK.

---

## 6. Rejection Codes

`REGIME_INCOMPATIBLE` | `HTF_MTF_MISALIGNMENT` | `TREND_CONFLICT` | `INSUFFICIENT_CONFIDENCE` |
`NEWS_BLOCKED` | `SPREAD_TOO_WIDE` | `VOLATILITY_ABNORMAL_HIGH` | `MARKET_NOT_READY` |
`INDICATOR_NOT_CONFIGURED` | `DUPLICATE_SIGNAL_ACTIVE` | `SIGNAL_EXPIRED` | `SETUP_INVALIDATED` |
`RISK_ENGINE_REJECTED` | `RISK_ENGINE_EMERGENCY` | `RISK_ENGINE_UNAVAILABLE`

---

## 7. Explainability

For any `signal_id`, system must answer: regime, HTF/MTF structure, trend, momentum, volatility,
spread, news state, confidence score, rejection reasons, Risk Engine rule.

Achieved through `EvidenceRecord` stored with every signal (forwarded and rejected alike).

---

## 8. Contract Compatibility

Additive to `contracts/signal.schema.json` and `brain/strategy/interfaces.py`.
Breaking changes require ADR.
