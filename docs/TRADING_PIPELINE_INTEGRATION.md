# AUREXIS Trading Pipeline Integration — Stage D

> **Status:** IMPLEMENTED — 2026-09-07
> **Authority:** `docs/MASTER_SPECIFICATION.md` v1.0 (LOCKED)
> **Mode:** SIMULATION ONLY — Live trading remains DISABLED

---

## 1. Architecture Overview

Stage D introduces the canonical end-to-end trading simulation pipeline.

```
Tick (MOCK / REPLAY)
  │
  ▼
MultiTimeframeBarManager (M5, M15, H1 BarBuilders)
  │
  ▼ (closed bars, staleness check, spread check)
  │
Brain SignalPipeline (PROPOSE only)
  ├── Structure analysis (closed bars, swing detection)
  ├── Regime classification (EMAs, ADX, RSI)
  ├── Setup detection (breakout, fakeout, continuation)
  └── Multi-factor confidence scoring
  │
  ▼ CandidateSignal
  │
[Gate: direction == NONE? → return SIGNAL_NONE]
[Gate: is_configured == False? → return SIGNAL_NONE]
  │
PostgreSQL: persist CandidateSignal (candidate_signals)
WS: emit SIGNAL_CREATED
  │
[Gate: signal expired? → return SIGNAL_EXPIRED]
  │
Risk Engine (evaluate_and_record_risk)
  ├── load RiskConfiguration from DB
  ├── build AccountRiskSnapshot from DB
  └── evaluate: NOT_CONFIGURED / BLOCKED / EMERGENCY / APPROVED
  │
PostgreSQL: persist RiskDecision (risk_decisions)
WS: emit RISK_STATE_CHANGED
  │
[Gate: NOT_CONFIGURED / BLOCKED / EMERGENCY? → return blocked status]
  │
ExecutionService.execute_approved_signal
  ├── idempotency check (execution_commands.idempotency_key)
  ├── create DbExecutionCommand
  ├── MT5AgentSimulator.execute_command (SIMULATION, is_simulated=True)
  ├── create DbExecutionReport
  └── create DbPosition (if FILLED)
  │
WS: emit COMMAND_CREATED → COMMAND_UPDATED → POSITION_UPDATED
  │
ReconciliationEngine
  ├── compare DB positions vs simulator positions
  ├── detect ORPHAN / PHANTOM / VOLUME_MISMATCH / SIDE_MISMATCH
  └── if critical → freeze account (circuit breaker)
  │
WS: emit SYSTEM_ALERT (if critical discrepancy)
PostgreSQL: AuditLog chain
  │
  ▼
PipelineCycleResult
```

---

## 2. Orchestrator: `TradingPipeline`

**File:** `backend/services/trading_pipeline.py`

### 2.1 Instantiation

```python
TradingPipeline(
    account_id: uuid.UUID,
    symbol: str = "XAUUSD",
    bar_manager: MultiTimeframeBarManager | None = None,
    brain_pipeline: SignalPipeline | None = None,
    simulator: MT5AgentSimulator | None = None,
    execution_service: ExecutionService | None = None,
    ws_manager: ConnectionManager | None = None,
    primary_timeframe: str = "M5",
    signal_expiry_seconds: int = 60,
)
```

`TradingPipeline.MODE = "SIMULATION"` — explicit constant.

### 2.2 Main Method

```python
async def process_tick(
    session: AsyncSession,
    tick: Tick,
    news_state: str = "CLEAR",
    correlation_id: str | None = None,
) -> PipelineCycleResult:
```

### 2.3 Reconciliation Circuit Breaker

```python
def freeze_account(self, account_id: uuid.UUID, reason: str) -> None
def unfreeze_account(self, account_id: uuid.UUID) -> None
def is_account_frozen(self, account_id: uuid.UUID) -> bool
```


---

## 3. Data Flow and State Transitions

| Stage | Action | DB Write | WS Event |
|-------|--------|----------|----------|
| Tick validation | `validate_tick()` | — | — |
| Bar ingestion | `ingest_tick()` | — | — |
| Staleness / spread gate | `is_stale()`, `is_spread_acceptable()` | — | — |
| Circuit breaker | `is_account_frozen()` | — | — |
| Brain pipeline | `brain_pipeline.process()` | — | — |
| Candidate signal | Persist `DbCandidateSignal` | `candidate_signals` | `SIGNAL_CREATED` |
| Risk evaluation | `evaluate_and_record_risk()` | `risk_decisions` + `audit_logs` | `RISK_STATE_CHANGED` |
| Execution command | `execute_approved_signal()` | `execution_commands` | `COMMAND_CREATED` |
| Execution report | Simulator fills | `execution_reports` | `COMMAND_UPDATED` |
| Position | Create `DbPosition` | `positions` | `POSITION_UPDATED` |
| Reconciliation | `reconcile_account_positions()` | `audit_logs` | `SYSTEM_ALERT` (if critical) |

---

## 4. Fail-Safe Gates (ordered)

| Gate | Condition | Status returned | Execution? |
|------|-----------|-----------------|-----------|
| 1 | Tick invalid (neg price, crossed spread, out-of-order) | `INVALID_TICK` | NO |
| 2 | Market stale (tick age > threshold) | `MARKET_DATA_NOT_READY` | NO |
| 3 | Spread too wide | `MARKET_DATA_NOT_READY` | NO |
| 4 | No closed bars (warming up) | `MARKET_DATA_NOT_READY` | NO |
| 5 | Account frozen (reconciliation circuit breaker) | `ACCOUNT_FROZEN` | NO |
| 6 | Brain: `direction == NONE` OR `is_configured == False` | `SIGNAL_NONE` | NO |
| 7 | Signal expired (`expires_at` in past) | `SIGNAL_EXPIRED` | NO |
| 8 | Risk: `NOT_CONFIGURED` | `RISK_NOT_CONFIGURED` | NO |
| 9 | Risk: `BLOCKED` | `RISK_BLOCKED` | NO |
| 10 | Risk: `EMERGENCY` | `RISK_EMERGENCY` | NO |
| 11 | Duplicate idempotency key | `EXECUTION_REJECTED` | NO |
| 12 | Simulator: unknown/rejected action | `EXECUTION_REJECTED` | NO |

---

## 5. Hard Safety Invariants

1. **Brain cannot create ExecutionCommand.** `SignalPipeline` is import-isolated; only produces `CandidateSignal`.
2. **Risk APPROVED is the only execution gate.** `execute_approved_signal()` checks `decision.trading_allowed`.
3. **Simulation label explicit.** All simulator fills carry `is_simulated=True`. `MT5AgentSimulator.MODE = "SIMULATION"`.
4. **Live broker unreachable.** No live broker connection, credentials, or socket code in this pipeline.
5. **`trading_enabled=False` preserved.** Pipeline never sets or queries `trading_enabled`. Account field remains `False`.
6. **Idempotent dispatch.** `DbExecutionCommand.idempotency_key` is unique-indexed. Duplicate keys return `None` without re-executing.
7. **Reconciliation circuit breaker.** `ORPHAN`, `VOLUME_MISMATCH`, or `SIDE_MISMATCH` freezes account for new entries.
8. **UTC timestamps everywhere.** `generated_at`, `expires_at`, `executed_at`, `decided_at` all UTC-aware.
9. **Decimal financial values.** No float arithmetic in risk, execution, or position fields.
10. **Account isolation.** `TradingPipeline` is scoped to exactly one `account_id`.
11. **Correlation ID propagation.** `correlation_id` flows through every downstream record.

---

## 6. Simulation-only Behavior

- `MT5AgentSimulator` is the only execution agent. It maintains in-memory `_positions: dict[int, PositionReport]`.
- `get_open_positions()` returns current simulated positions for reconciliation.
- Simulator explicitly marked `MODE = "SIMULATION"` — no live MT5 socket, no real broker.

---

## 7. Known Limitations

1. **PostgreSQL not running locally** (Docker not on machine): DB writes verified against SQLite in-memory via pytest.
2. **Redis pub/sub not connected**: `ConnectionManager` WebSocket broadcasts tested via in-memory mock.
3. **Live broker credentials**: Not configured, not needed, intentionally absent.
4. **trading_enabled=True path**: Not exercisable — pipeline never sets `trading_enabled=True`.

---

## 8. Files

| File | Purpose |
|------|---------|
| `backend/services/trading_pipeline.py` | Canonical orchestrator |
| `backend/ws/events.py` | Added event constructors |
| `backend/execution/simulator.py` | Added position tracking, `get_open_positions` |
| `backend/services/execution_service.py` | Added idempotency check, price forwarding |
| `brain/market_data/multi_timeframe.py` | Cleaned stray field annotation |
| `tests/test_trading_pipeline.py` | 17 integration tests (happy path + negative matrix + invariants) |
| `docs/TRADING_PIPELINE_INTEGRATION.md` | This document |

