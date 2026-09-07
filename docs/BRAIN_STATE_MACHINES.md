# AUREXIS Brain State Machines

> **Status:** DRAFT — 2026-09-06
> **Authority:** `docs/MASTER_SPECIFICATION.md` v1.0 (LOCKED)

---

## 1. Market Data State Machine

```
INITIALIZING
    → WARMING_UP       (historical data load begins)
    → READY            (min bar count satisfied on all timeframes)
    → DEGRADED         (insufficient history for one+ timeframes)
    → STALE            (no tick within staleness threshold — UNDEFINED)
    → RECONNECTING     (feed disconnect)
    → CLOSED           (market closure)

STALE → READY          (fresh tick received)
RECONNECTING → WARMING_UP   (feed reconnected — must re-validate)
CLOSED → WARMING_UP    (market reopen)
DEGRADED → READY       (history supplemented)
Any → CLOSED           (closure signal)
Any → RECONNECTING     (disconnect)
Any → UNKNOWN_ERROR    (unrecoverable — requires manual reset)
```

**In any non-READY state: NO candidate signals.**

---

## 2. Regime State Machine

See `docs/REGIME_SPECIFICATION.md` for full definition.

States: `UNKNOWN`, `TREND_UP`, `TREND_DOWN`, `RANGE`, `TRANSITION`, `HIGH_VOLATILITY`

All transitions require N-bar hysteresis (N: UNDEFINED).
HIGH_VOLATILITY may have N=1 (design consideration, not locked).
`UNKNOWN` on any insufficient data or contradiction.

---

## 3. Setup State Machine

```
IDLE
    → CANDIDATE_FORMING     (evidence accumulating; not yet a signal)
    → SETUP_READY           (all setup conditions met)
    → SETUP_INVALIDATED     (market moved against setup; back to IDLE)

SETUP_READY
    → CANDIDATE_READY       (proceeds to signal lifecycle)
    → SETUP_INVALIDATED     (market moved; back to IDLE)
    → SETUP_EXPIRED         (time window elapsed; back to IDLE)
```

Only one active setup per account per instrument.
A new setup cannot form while `SETUP_READY` is active.

---

## 4. Candidate Signal State Machine

```
CANDIDATE_FORMING
    → CANDIDATE_READY       (minimum evidence threshold met)
    → INVALIDATED           (setup broken — terminal)

CANDIDATE_READY
    → NEWS_BLOCKED          (news state non-CLEAR)
    → PENDING_RISK          (news CLEAR; submitted to Risk Engine)
    → EXPIRED               (validity window elapsed — terminal)
    → INVALIDATED           (market moved against reference — terminal)

NEWS_BLOCKED
    → CANDIDATE_READY       (news clears — re-evaluate)
    → EXPIRED               (validity elapsed while blocked — terminal)
    → INVALIDATED           (market moved — terminal)

PENDING_RISK
    → RISK_APPROVED         (Risk Engine returned APPROVED)
    → RISK_REJECTED         (Risk Engine BLOCKED/NOT_CONFIGURED — terminal)
    → RISK_EMERGENCY        (Risk Engine EMERGENCY — terminal)
    → EXPIRED               (Risk Engine timeout — terminal)

RISK_APPROVED
    → FORWARDED             (handed to Execution Engine — terminal, Brain done)
    → EXPIRED               (execution window elapsed — terminal)
```

Terminal states: `INVALIDATED`, `EXPIRED`, `RISK_REJECTED`, `RISK_EMERGENCY`, `FORWARDED`.
Only one signal per account in `PENDING_RISK` at a time.

---

## 5. Risk Decision State Machine

(Defined in `backend/risk/engine.py` — summarized here for Brain interaction)

```
PENDING → APPROVED
        → BLOCKED
        → NOT_CONFIGURED
        → EMERGENCY
```

Brain receives result synchronously. All states except `APPROVED` result in NO execution.
Brain cannot re-submit same signal after rejection. Must wait for new setup.

---

## 6. Execution Handoff State Machine

(Defined in `docs/EXECUTION_ENGINE.md` — Brain's view)

```
NOT_STARTED
    → FORWARDED_TO_EXECUTION    (Brain responsibility ends)

From Execution Engine feedback (observability only):
    → EXECUTION_ACKNOWLEDGED
    → EXECUTION_FILLED
    → EXECUTION_REJECTED
    → EXECUTION_EXPIRED
```

Brain observes execution feedback for auditing. Brain does NOT re-enter the execution path.

---

## 7. State Machine Implementation Rules

- No implicit boolean flags where a state enum is appropriate
- State transitions emit structured log events
- All terminal states are logged with full evidence
- Invalid transition attempts are logged as errors and rejected
- State must be recoverable on Brain restart (persisted to Redis or reconstructed from last known state)
- Multi-account: each account has independent setup and signal state machines
- Market data state machine is shared (XAUUSD feed is shared)
