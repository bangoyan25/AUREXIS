# AUREXIS Brain Specification

> **Status:** LOCKED (architecture+pipeline approved 2026-09-06; empirical parameters remain UNDEFINED) — 2026-09-06
> **Authority:** Derived from `docs/MASTER_SPECIFICATION.md` v1.0 (LOCKED)
> **No production trading parameters defined here. All numerical thresholds are UNDEFINED.**

---

## 1. Brain Identity

The Brain is the server-side market analysis and signal-generation engine.

It is NOT a trading robot, risk engine, or execution engine.

The Brain produces **candidate signals** — structured recommendations — that must pass through the Risk Engine before any execution is considered.

---

## 2. Responsibilities

**IS responsible for:**

- Receiving and normalizing raw XAUUSD market ticks
- Maintaining stateful market representation
- Computing market structure (swing points, breaks of structure)
- Computing regime (trend, range, transition, high-volatility, unknown)
- Computing trend direction and strength
- Detecting breakout and fakeout setups
- Computing momentum context (independent dimension from trend)
- Computing volatility context (ATR-class metric or equivalent)
- Multi-factor evidence assembly
- Signal scoring and confidence filtering
- Producing `CandidateSignal` with full evidence provenance
- Structured observability events for every state change
- Signal expiry enforcement
- Strategy versioning

**NOT responsible for:**

- Approving/rejecting trades (Risk Engine authority)
- Sending commands to MT5 (Execution Engine)
- Account state or equity management
- Applying news blackout windows (queries News Engine, does not own it)
- Persisting own history (market data service)
- Authentication (API/Auth layer)
- Position sizing (Risk Engine / Sizing module)

---

## 3. Inputs

### 3.1 Market Tick (minimum required fields)

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Always `XAUUSD` |
| `bid` | `Decimal` | Bid price |
| `ask` | `Decimal` | Ask price |
| `timestamp` | `datetime` UTC | Broker tick timestamp |
| `received_at` | `datetime` UTC | Server receipt timestamp |

Optional: `volume` (`Decimal` or `None`), `broker_symbol` (`str`).

### 3.2 Historical Bar Data

Multi-timeframe OHLCV bars for indicator bootstrap.
Exact timeframe values: **CONFIGURABLE** (see `docs/REGIME_SPECIFICATION.md`).
Fields per bar: `open`, `close`, `high`, `low`, `volume`, `bar_time` (UTC), `timeframe`.

### 3.3 News Engine State

```
NewsState := CLEAR | PRE_EVENT | IN_EVENT | POST_EVENT | UNKNOWN | PROVIDER_UNAVAILABLE | STALE
```

If `NewsState != CLEAR` → NO candidate signal.

### 3.4 Configuration

All parameters requiring empirical approval: **CONFIGURABLE / UNDEFINED**:

- Timeframe periods, indicator parameters, scoring weights
- Confidence threshold, minimum confirmations
- Staleness threshold, spread threshold, jump threshold

Brain returns `NOT_CONFIGURED` when any required parameter is `None`.

---

## 4. Outputs

### 4.1 CandidateSignal

Defined in `brain/strategy/interfaces.py`. Full schema in `docs/SIGNAL_MODEL.md`.

NOT an order. A recommendation with evidence.

```
CandidateSignal → News gate → Risk Engine
    → [APPROVED] → Execution Engine
    → [REJECTED / BLOCKED / EMERGENCY] → discard + log
```

### 4.2 Observability Events

Structured events at every significant state transition (see §12).

---

## 5. Market State Lifecycle

```
INITIALIZING → WARMING_UP → READY ⇄ STALE
                                   ⇄ DEGRADED
                                   ⇄ RECONNECTING → WARMING_UP
                            CLOSED ⇄ WARMING_UP
```

| From | To | Trigger |
|------|----|---------|
| `INITIALIZING` | `WARMING_UP` | Historical data load begins |
| `WARMING_UP` | `READY` | Min bar count satisfied on all timeframes |
| `WARMING_UP` | `DEGRADED` | Insufficient history on one+ timeframe |
| `READY` | `STALE` | No tick within staleness threshold (UNDEFINED) |
| `STALE` | `READY` | Fresh tick received |
| `READY` | `RECONNECTING` | Feed disconnect |
| `RECONNECTING` | `WARMING_UP` | Feed reconnected |
| Any | `CLOSED` | Market closure signal |
| `CLOSED` | `WARMING_UP` | Market reopen |

**Non-`READY` state: NO candidate signals.**

---

## 6. Tick Processing Pipeline

```
1.  Receive raw tick
2.  Validate fields (bid/ask/timestamp/symbol non-null)
3.  Timestamp checks:
    a. Duplicate (same as last)         → discard
    b. Out-of-order (< last timestamp)  → discard + log
    c. Future timestamp                 → discard + log
    d. Staleness threshold exceeded     → enter STALE
4.  Normalize (Decimal, mid-price, spread)
5.  Update market data state
6.  Update bar aggregators (each configured timeframe)
    → bar close triggers bar-close calculations for that TF
7.  Update tick-level indicators (if any)
8.  Update bar-level indicators (bar close ONLY — no look-ahead)
9.  Update market structure (bar close ONLY)
10. Update regime classifier
11. Evaluate active setup
12. Evaluate candidate signal (only if regime tradeable)
13. Check news state → if not CLEAR, hold or expire
14. Score and confidence-filter
15. If sufficient → pass to Risk Engine
16. Emit observability events
```

### Tick anomaly table

| Condition | Action |
|-----------|--------|
| Rapid burst | Process sequentially for state; rate-limit signal generation |
| Abnormal price jump (> threshold UNDEFINED) | Update state, no signal on that tick |
| Spread too wide (> threshold UNDEFINED) | Block signal, emit `spread_too_wide` |
| Session transition | Attach session label to state; no auto filter |

---

## 7. Signal Lifecycle

```
CANDIDATE_FORMING
    → CANDIDATE_READY
        → NEWS_BLOCKED ⇄ CANDIDATE_READY (re-check)
        → PENDING_RISK
            → RISK_APPROVED → FORWARDED (terminal, Brain done)
            → RISK_REJECTED (terminal)
        → EXPIRED (terminal)
        → INVALIDATED (terminal)
```

Rules:
- Only one signal per account in `PENDING_RISK` at a time.
- No new setup signal while existing is `PENDING_RISK`.

---

## 8. Risk Engine Interaction

Brain calls: `RiskEngine.evaluate(AccountRiskSnapshot, CandidateSignal)`
Receives: `RiskDecision`

**Brain cannot override REJECTED or BLOCKED.**

If Risk Engine unavailable: treat as `NOT_CONFIGURED`, no execution, log + emit `risk_engine_unavailable`.

---

## 9. News Engine Interaction

Before forwarding signal:
1. Query `NewsState` for XAUUSD / USD
2. `CLEAR` → proceed to Risk Engine
3. Else → `NEWS_BLOCKED`, re-check periodically
4. Signal expiry while blocked → `EXPIRED`

If News Engine unavailable / UNKNOWN → treat as `PRE_EVENT` → NO signal.

---

## 10. Execution Engine Interaction

Brain passes `RISK_APPROVED` signal to Execution Engine → signal moves to `FORWARDED`.
Brain responsibility ends at `FORWARDED`.
Brain receives execution feedback for observability only — not to re-enter execution path.

---

## 11. Fail-Safe Rules

| Condition | Brain Action |
|-----------|-------------|
| Market state not READY | NO signal |
| Indicators not warmed up | NO signal |
| Staleness exceeded | NO signal + `market_data_stale` |
| Spread too wide | NO signal + `spread_too_wide` |
| News UNKNOWN / unavailable | NO signal + `news_state_unknown` |
| News PRE/IN/POST_EVENT | NO signal |
| Confidence below threshold | NO signal + `signal_rejected_confidence` |
| Regime UNKNOWN | NO signal |
| Structure INSUFFICIENT_DATA | NO signal |
| Conflicting evidence | NO signal + `signal_evidence_conflict` |
| Risk Engine unavailable | NO signal + `risk_engine_unavailable` |
| Strategy NOT_CONFIGURED | NO signal |
| Any required parameter None | NO signal |

**Default on any uncertainty: NO TRADE.**

---

## 12. Observability Events

| Event | Trigger | Level |
|-------|---------|-------|
| `brain.market_state_changed` | State machine transition | INFO |
| `brain.regime_changed` | Regime transition | INFO |
| `brain.structure_changed` | Structure update | INFO |
| `brain.setup_detected` | New setup | INFO |
| `brain.setup_invalidated` | Setup cancelled | INFO |
| `brain.candidate_signal_generated` | Signal → CANDIDATE_READY | INFO |
| `brain.signal_news_blocked` | News gate blocking | INFO |
| `brain.signal_confidence_rejected` | Score below threshold | INFO |
| `brain.signal_evidence_conflict` | Conflicting indicators | INFO |
| `brain.signal_forwarded_to_risk` | Sent to Risk Engine | INFO |
| `brain.signal_risk_approved` | Risk approved | INFO |
| `brain.signal_risk_rejected` | Risk rejected | WARNING |
| `brain.signal_expired` | Validity elapsed | INFO |
| `brain.signal_invalidated` | Market moved against reference | INFO |
| `brain.signal_forwarded_to_execution` | Handed to Execution Engine | INFO |
| `brain.market_data_stale` | Staleness exceeded | WARNING |
| `brain.spread_too_wide` | Spread over max | WARNING |
| `brain.news_state_unknown` | News Engine unavailable | WARNING |
| `brain.risk_engine_unavailable` | Risk Engine failed | ERROR |
| `brain.indicator_not_configured` | Required param None | WARNING |

Every event: `account_id`, `symbol`, `timestamp` (UTC), `strategy_version`, `correlation_id`.
No secrets logged. No raw tick spam at WARNING+.

---

## 13. Versioning

Format: `"{MAJOR}.{MINOR}.{PATCH}-{label}"`
Current: `"0.0.0-not-configured"` — no production strategy implemented.

Version included in every `CandidateSignal`, command, and audit log entry.

---

## 14. Multi-Account Behavior

- Tick feed and market state computation: shared (XAUUSD)
- Per-account signal lifecycle and active setup: strictly isolated
- Account A state must never influence Account B evaluation

---

*All UNDEFINED parameters tracked in `docs/STRATEGY_SPECIFICATION.md` Appendix A.*

