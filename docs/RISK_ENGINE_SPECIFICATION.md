# AUREXIS Risk Engine Production Specification

> **Status:** LOCKED � Owner Decisions Approved 2026-09-06  
> **Authority:** Derived from `docs/MASTER_SPECIFICATION.md` v1.0 (LOCKED)  
> **Initial Instrument:** XAUUSD only  
> **Initial Broker Target:** Standard MT5 Broker (Cent Account / Standard Account)  
> **Initial Account Scope:** 1 Account (Scalable to 5+ Isolated Accounts)  
> **Mandatory Rule:** All numerical risk parameters and empirical thresholds not explicitly locked are **UNDEFINED**. No agent may invent them.

---

## 1. Purpose

The Risk Engine is the authoritative, non-bypassable, fail-closed gatekeeper of AUREXIS capital.

```
Brain (CandidateSignal) ? [ RISK ENGINE ] ? APPROVED ? Execution Engine ? MT5
                                ?
                          BLOCKED / EMERGENCY ? Discard + Audit Log
```

Core axiom:
> **The Brain may propose. The Risk Engine decides. The Execution Engine executes only approved commands.**

This specification deterministically defines when AUREXIS is permitted or forbidden to authorize a new trade entry or manage existing risk.

---

## 2. Scope

### In Scope
- Risk state machine lifecycle (`NOT_CONFIGURED`, `NORMAL`, `CAUTION`, `PROTECTED`, `STOPPED`, `EMERGENCY_STOP`).
- Candidate signal evaluation and trade entry gating.
- Daily loss limits, maximum drawdown thresholds, and position/lot exposure limits.
- Dynamic profit-lock state management and floor calculations.
- Market data staleness and spread condition gating.
- Economic news event blackout gating.
- Atomic trade authorization and concurrency control.
- Deterministic idempotency and deduplication.
- Audit trail emission for every decision.
- Absolute isolation across multiple trading accounts.

### Out of Scope
- Market analysis, regime classification, or predictive calculations (Brain responsibility).
- Direct order placement or MT5 socket communications (Execution Engine / MT5 EA responsibility).
- Database persistence mechanics (Backend DB layer).
- UI presentation or client-side calculation (Frontend layer).

---

## 3. Principles

1. **Authority:** No trade command reaches MT5 without explicit `SignalDecision.APPROVED`.
2. **Fail-Closed:** Any `UNKNOWN`, `STALE`, `DEGRADED`, or `NOT_CONFIGURED` critical state ? `BLOCKED` for new entries.
3. **Determinism:** Same inputs + same config ? identical decision in live and backtest.
4. **Capital First:** Risk limits are immutable. No profit objective may weaken any risk control.
5. **Decimal Only:** All monetary risk calculations use `Decimal` / PostgreSQL `NUMERIC`. Float forbidden in risk paths.
6. **Auditable:** Every evaluation emits an immutable structured record.

---

## 4. Terminology

| Term | Definition |
|---|---|
| `CandidateSignal` | Brain's structured trade recommendation. Not an order. |
| `RiskDecision` | Verdict: `APPROVED` \| `BLOCKED` \| `NOT_CONFIGURED` \| `EMERGENCY`. |
| `AccountRiskSnapshot` | Point-in-time account state normalized to USD. |
| `Normalized USD` | Authoritative unit after `cent_normalization_factor` applied. |
| `High-Water Mark (HWM)` | Peak equity reference point used to measure drawdown and profit lock. |
| `Protected Floor` | Minimum equity level established by dynamic profit-lock to preserve gains. |
| `Drawdown` | Monetary or percentage decline from reference peak equity to current equity. |
| `Daily Loss` | Cumulative net negative PNL incurred within active trading session day. |
| `Basket` | Aggregation of all open positions and active orders for one account/instrument scope. |
| `In-Flight Exposure` | Volume currently reserved by commands in transit to MT5. |

---

## 5. Inputs

### 5.1 Candidate Signal Context (`CandidateSignal`)
- `signal_id`: UUID (Unique per candidate signal)
- `account_id`: UUID (Target account binding)
- `symbol`: String (Canonical `XAUUSD`)
- `direction`: Enum (`BUY` \| `SELL`)
- `entry_reference`: `Decimal` (Expected entry price)
- `suggested_stop_loss`: `Decimal | None` (Brain invalidation level, algorithm: UNDEFINED)
- `suggested_take_profit`: `Decimal | None` (Brain structural target, algorithm: UNDEFINED)
- `confidence_score`: `Decimal | None` (Brain multi-factor score)
- `expires_at`: UTC `datetime` (Signal validity window)
- `strategy_version`: String (Brain model version)
- `correlation_id`: String (Distributed trace token)

### 5.2 Account Risk Snapshot Context (`AccountRiskSnapshot`)
- `account_id`: UUID
- `current_balance_usd`: `Decimal` (Closed trade balance normalized to USD)
- `current_equity_usd`: `Decimal` (Balance + floating PNL normalized)
- `equity_peak_usd`: `Decimal` (Peak equity reached in session/lifetime)
- `daily_realized_pnl_usd`: `Decimal` (Net realized PNL today including fees)
- `daily_floating_pnl_usd`: `Decimal` (Unrealized PNL of open positions)
- `open_position_count`: Integer (Currently active open positions)
- `open_lot_exposure`: `Decimal` (Total active open volume in lots)
- `in_flight_lot_exposure`: `Decimal` (Lots currently pending MT5 execution)
- `snapshot_at`: UTC `datetime` (Timestamp of snapshot generation)

### 5.3 Market Condition Context
- `symbol`: String (`XAUUSD`)
- `bid`: `Decimal`, `ask`: `Decimal`
- `spread`: `Decimal` (`ask - bid`)
- `tick_timestamp`: UTC `datetime` (Broker tick timestamp)
- `received_at`: UTC `datetime` (Server receipt timestamp)
- `market_data_status`: Enum (`READY` \| `DEGRADED` \| `STALE` \| `RECONNECTING` \| `CLOSED` \| `UNKNOWN`)

### 5.4 News Protection Context
- `news_state`: Enum (`CLEAR` \| `PRE_EVENT` \| `IN_EVENT` \| `POST_EVENT` \| `UNKNOWN` \| `PROVIDER_UNAVAILABLE` \| `STALE`)

### 5.5 Configuration Context (`RiskConfig`)
- `config_version`: String (Immutable configuration version tag)
- `daily_loss_limit_usd`: `Decimal | None` (**UNDEFINED**)
- `max_drawdown_usd`: `Decimal | None` (**UNDEFINED**)
- `caution_drawdown_pct`: `Decimal | None` (**UNDEFINED**)
- `max_open_positions`: Integer `| None` (**UNDEFINED**)
- `max_open_lots`: `Decimal | None` (**UNDEFINED**)
- `max_spread_usd`: `Decimal | None` (**UNDEFINED**)
- `max_tick_staleness_ms`: Integer `| None` (**UNDEFINED**)
- `profit_lock_formula`: String `| None` (**UNDEFINED**)
- `profit_lock_threshold_usd`: `Decimal | None` (**UNDEFINED**)
- `profit_lock_floor_pct`: `Decimal | None` (**UNDEFINED**)
- `emergency_stop_active`: Boolean (`False` by default)

`is_fully_configured` returns `True` only when all required fields are non-`None`. Any required field `None` ? `NOT_CONFIGURED`.

---

## 6. Outputs

The Risk Engine emits an immutable `RiskDecision`:

```python
@dataclass(frozen=True)
class RiskDecision:
    decision_id: str                      # Unique UUID for this decision
    decision: SignalDecision              # APPROVED | BLOCKED | NOT_CONFIGURED | EMERGENCY
    reason_code: str                      # Machine-readable token (e.g. ALL_CHECKS_PASSED)
    explanation: str                      # Human-readable audit narrative
    risk_state: RiskState                 # Operational state
    account_id: str                       # Target account UUID
    signal_id: str | None                 # Evaluated signal ID
    correlation_id: str                   # Trace token
    decided_at: datetime                  # UTC timestamp
    config_version: str                   # Active risk configuration version
    authorized_lot_size: Decimal | None   # Final risk-authorized volume (None if not APPROVED)
    equity_at_decision: Decimal           # Snapshot equity at evaluation
    drawdown_at_decision: Decimal         # Evaluated drawdown at evaluation
    daily_pnl_at_decision: Decimal        # Realized/combined daily PNL evaluated
    evaluated_limits: dict[str, Any]      # Limits checked and evaluated values
```

`trading_allowed` is `True` strictly when `decision == SignalDecision.APPROVED`.

---

## 7. Risk State Machine

### 7.1 State Definitions

1. **`NOT_CONFIGURED`**: Default. One or more mandatory risk configuration parameters are `None`. All signals rejected.
2. **`NORMAL`**: Account within all approved limits. New trade authorization permitted when candidate signals satisfy all checks.
3. **`CAUTION`**: Account approaching risk boundaries (drawdown approaching limit, open positions at cap, spread elevated). No new trade entries permitted. Open positions monitored; SL/TP adjustments permitted.
4. **`PROTECTED`**: Dynamic profit-lock active. Account equity reached or exceeded activation threshold. New trade entries gated or forbidden. Floor protection active.
5. **`STOPPED`**: Daily loss limit hit, maximum drawdown hit, or dynamic profit floor breached. All new entries forbidden for remainder of trading session.
6. **`EMERGENCY_STOP`**: System or operator kill switch active. Immediate halt of all new commands. Recovery requires operator override.

### 7.2 Formal State Transition Table

| Current State | Condition | Next State | Action Taken |
|---|---|---|---|
| `NOT_CONFIGURED` | `is_fully_configured == True` | `NORMAL` | Enable signal evaluation. Log INFO. |
| `NORMAL` | Any required config field set to `None` | `NOT_CONFIGURED` | Block entries. Log WARNING. |
| `NORMAL` | `emergency_stop_active == True` | `EMERGENCY_STOP` | Halt trading. Emit emergency alert. |
| `NORMAL` | `CURRENT_DRAWDOWN >= max_drawdown_usd * caution_drawdown_pct` | `CAUTION` | Block new entries. Retain positions. |
| `NORMAL` | `open_positions + 1 > max_open_positions` | `CAUTION` | Block new entry (`MAX_POSITIONS_REACHED`). |
| `NORMAL` | `SESSION_PROFIT >= profit_lock_threshold_usd` | `PROTECTED` | Compute floor. Emit `PROFIT_LOCK_ACTIVE`. |
| `NORMAL` | `DAILY_LOSS >= daily_loss_limit_usd` | `STOPPED` | Block new entries. Emit `DAILY_LOSS_LIMIT_HIT`. |
| `NORMAL` | `CURRENT_DRAWDOWN >= max_drawdown_usd` | `STOPPED` | Block new entries. Emit `MAX_DRAWDOWN_HIT`. |
| `CAUTION` | `open_positions < max_open_positions` AND drawdown clears caution band | `NORMAL` | Restore trade authorization. |
| `CAUTION` | `DAILY_LOSS >= daily_loss_limit_usd` | `STOPPED` | Block entries for session. |
| `CAUTION` | `CURRENT_DRAWDOWN >= max_drawdown_usd` | `STOPPED` | Block entries. Emit `MAX_DRAWDOWN_HIT`. |
| `CAUTION` | `emergency_stop_active == True` | `EMERGENCY_STOP` | Halt trading immediately. |
| `PROTECTED` | `CURRENT_EQUITY <= PROTECTED_FLOOR` | `STOPPED` | Lock profit. Trigger basket close. |
| `PROTECTED` | `CURRENT_EQUITY > SESSION_PEAK` | `PROTECTED` | Update peak, recalculate floor. |
| `PROTECTED` | Session boundary reset crossed | `NORMAL` | Reset session peak and profit floor (Open Decision #4). |
| `STOPPED` | Session boundary reset (daily loss cause only) | `NORMAL` | Reset daily loss accumulator if equity above limits. |
| `STOPPED` | Drawdown persists >= `max_drawdown_usd` | `STOPPED` | Remain STOPPED. Operator review required. |
| `Any State` | State corruption, reconciliation failure, impossible values | `EMERGENCY_STOP` | Halt all trading unconditionally. |
| `EMERGENCY_STOP` | Explicit operator clear + state verified clean | `NORMAL` | Manual re-authorization with audit log. |

### 7.3 Action Matrix by State

| State | New Entry Allowed | Hold Existing Positions | Position Close / Reduction | SL/TP Move | Brain Signal Accepted | Execution Command Created |
|---|---|---|---|---|---|---|
| `NOT_CONFIGURED` | NO | YES | YES | YES | NO (returns `NOT_CONFIGURED`) | NO |
| `NORMAL` | YES | YES | YES | YES | YES | YES (if approved) |
| `CAUTION` | NO | YES | YES | YES | NO (returns `BLOCKED`) | Close / Mod only |
| `PROTECTED` | NO* | YES | YES | YES | NO* | Close / Mod only |
| `STOPPED` | NO | YES (Controlled) | YES | YES | NO (returns `BLOCKED`) | Close only |
| `EMERGENCY_STOP` | NO | Policy TBD | YES (Emergency close) | NO | NO (returns `EMERGENCY`) | Emergency close only |

*\*Note: New trade entries in `PROTECTED` state are FORBIDDEN unless a formal multi-trade profit reinvestment policy is approved.*

---

## 8. Daily Loss Control

### 8.1 Formulas

Let E0 = Starting Equity at session start (normalized USD).
At time T:
- R(T) = Cumulative realized PNL from closed trades since session start.
- F(T) = Net floating unrealized PNL of open positions at T.
- C(T) = Commissions paid since session start.
- S(T) = Swap/financing fees paid or credited since session start.
- D(T), W(T), A(T) = Deposits, withdrawals, and broker adjustments since session start.

Capital adjustment (external):
  delta_external(T) = D(T) - W(T) + A(T)

Daily net PNL:
  DAILY_PNL(T) = CURRENT_EQUITY(T) - E0 - delta_external(T)

Daily loss magnitude:
  DAILY_LOSS(T) = max(0, -DAILY_PNL(T))

### 8.2 Enforcement

  DAILY_LOSS(T) >= daily_loss_limit_usd => STOPPED, reason: DAILY_LOSS_LIMIT_HIT

All new entries BLOCKED for session. Open position treatment: Open Decision #6.

### 8.3 Boundaries

- Session reset timezone: UNDEFINED (Open Decision #1). Candidates: UTC 00:00, Broker Server Time 00:00.
- At reset: If drawdown < max_drawdown_usd, daily loss accumulator resets to 0 and state transitions STOPPED -> NORMAL.
- External capital adjustments (D, W, A) are excluded from daily loss accumulation.

---

## 9. Maximum Drawdown

### 9.1 Benchmark Reference Options

Product owner must select one reference benchmark:
- Option A: Lifetime High-Water Mark (HWM) - highest equity ever reached on account.
- Option B: Session Peak Equity - highest equity reached today.
- Option C: Initial Account Equity - fixed equity at account creation.
- Option D: Peak Closed Balance - highest closed-trade balance achieved.

Current status: UNDEFINED (Open Decision #2).

### 9.2 Formulas

Given reference peak HWM(T):
  CURRENT_DRAWDOWN(T) = max(0, HWM(T) - CURRENT_EQUITY(T))
  DRAWDOWN_PCT(T) = (CURRENT_DRAWDOWN(T) / HWM(T)) * 100%

### 9.3 Enforcement

- Caution: CURRENT_DRAWDOWN(T) >= max_drawdown_usd * caution_drawdown_pct => CAUTION
- Stop: CURRENT_DRAWDOWN(T) >= max_drawdown_usd => STOPPED, reason: MAX_DRAWDOWN_HIT

---

## 10. Position and Exposure Limits

### 10.1 Monitored Dimensions

1. Position count: N_open + N_in_flight >= max_open_positions => BLOCKED (MAX_POSITIONS_REACHED)
2. Total lot volume: lots_open + lots_in_flight + lots_proposed > max_open_lots => BLOCKED (MAX_LOTS_EXCEEDED)
3. Net directional exposure: abs(sum BUY lots - sum SELL lots) (limit: UNDEFINED)
4. Notional margin exposure: Used margin limit (limit: UNDEFINED)

### 10.2 Race-Condition Prevention (In-Flight Reservations)

Simultaneous signals arriving milliseconds apart are prevented from double-allocating through atomic in-flight reservations:
  Effective Count = N_open + N_in_flight
  Effective Lots = lots_open + lots_in_flight + lots_proposed

Reservation is created atomically at signal approval. Released when MT5 confirms FILLED, REJECTED, or EXPIRED.

---

## 11. Position Sizing Interface

### 11.1 Role Separation

| Component | Responsibility |
|---|---|
| Brain | Provides suggested_stop_loss (price level) and suggested_take_profit. Does NOT compute lot size. |
| Risk Engine / Sizing Module | Computes risk-authorized lot size from equity, risk parameters, stop distance, constraints. |
| Execution Engine | Sends exactly authorized_lot_size to MT5. Not the Brain suggestion. |

### 11.2 Variables Required (Not Yet Approved)

- risk_per_trade_pct OR risk_per_trade_usd: UNDEFINED (Open Decision #3)
- stop_distance_price_units = abs(entry_reference - suggested_stop_loss)
- pip_value_per_lot (symbol contract spec, broker-specific)
- max_lot_per_trade: UNDEFINED
- lot_step (broker minimum lot increment)

Production sizing formula: UNDEFINED (Open Decision #3).

### 11.3 Output Contract

RiskDecision.authorized_lot_size:
- Non-None only when decision == APPROVED.
- Final lot size used by Execution Engine -- overrides any Brain suggestion.

---

## 12. Basket Risk

### 12.1 Basket Identity

One basket = all positions + in-flight orders for same account_id + symbol (XAUUSD).

### 12.2 Basket State Variables

| Variable | Status |
|---|---|
| basket_unrealized_pnl_usd | Sum of floating PNL across all open positions |
| basket_realized_pnl_usd | Sum of closed trade PNL since session start |
| basket_lot_exposure | Sum of lots across open positions |
| basket_position_count | Count of open positions |
| max_basket_lot_exposure | Limit: UNDEFINED |
| max_basket_monetary_risk_usd | Limit: UNDEFINED |

### 12.3 Basket Closure on Profit-Lock Floor Breach

When CURRENT_EQUITY <= PROTECTED_FLOOR => STOPPED + basket closure triggered.
Closure mechanism and urgency: UNDEFINED (Open Decision #7).

---

## 13. Dynamic Profit-Lock

### 13.1 What Is Locked

- Concept approved: A rising protection level based on account equity peak progress.
- Direction: As session profit increases, protected floor rises monotonically.
- Owner: Risk Engine owns this computation. Brain does not compute it.

### 13.2 What Requires Owner Decision (All UNDEFINED)

- Profit-lock formula (Open Decision #4).
- Activation threshold profit_lock_threshold_usd (Open Decision #4).
- Floor percentage profit_lock_floor_pct (Open Decision #4).
- Stage structure: discrete tiers vs continuous (Open Decision #4).
- Daily session reset behavior (Open Decision #4).
- Floating vs realized equity basis (Open Decision #5).
- Partial-close vs full basket closure on floor breach (Open Decision #7).

### 13.3 Illustrative References from Repository

docs/RISK_ENGINE.md states examples: peak +$10 -> protection at -$3; peak +$20 -> protection at -$6.
docs/PRD.md states: "Do not hard-code examples as universal rules."
These examples establish the concept. They are NOT the production formula.

### 13.4 Candidate Formula Structures (Awaiting Selection)

Candidate A -- Fixed Percentage Retrace:
  PROTECTED_FLOOR_USD = SESSION_PEAK_PROFIT * (1 - profit_lock_floor_pct)

Candidate B -- Fixed USD Retrace:
  PROTECTED_FLOOR_USD = SESSION_PEAK_PROFIT - profit_lock_retrace_usd

Candidate C -- Tiered Stage System:
  Each tier crossing raises floor to new fixed ratio. Tiers and ratios: UNDEFINED.

None of A, B, C is the production formula. Owner must select.

### 13.5 State Variables

| Variable | Definition | Scope |
|---|---|---|
| profit_lock_active | Floor is active and monitored | Per account, per session |
| session_peak_equity_usd | Highest equity reached this session | Per account |
| session_start_equity_usd | Equity at session open | Per account |
| session_peak_profit_usd | session_peak_equity - session_start_equity | Per account |
| protected_floor_usd | Computed from formula -- UNDEFINED | Per account |
| profit_lock_threshold_usd | Minimum profit for activation | UNDEFINED |

### 13.6 State Machine

```
INACTIVE
  -> ACTIVE           (session_peak_profit >= profit_lock_threshold_usd)

ACTIVE
  -> PEAK_UPDATED     (CURRENT_EQUITY > session_peak -> update peak, recalculate floor)
  -> FLOOR_BREACHED   (CURRENT_EQUITY <= protected_floor)
  -> INACTIVE         (session reset -- behavior UNDEFINED, Open Decision #4)

FLOOR_BREACHED -> STOPPED + basket closure
```

Production formula: UNDEFINED (Open Decision #4).

---

## 14. News Protection Interaction

### 14.1 Decision Table by News State

| news_state | New Trade Authorization | Reason Code |
|---|---|---|
| CLEAR | PERMITTED | Proceed with evaluation |
| PRE_EVENT | BLOCKED | NEWS_PRE_EVENT |
| IN_EVENT | BLOCKED | NEWS_IN_EVENT |
| POST_EVENT | BLOCKED | NEWS_POST_EVENT |
| UNKNOWN | BLOCKED (fail-closed) | NEWS_STATE_UNKNOWN |
| PROVIDER_UNAVAILABLE | BLOCKED (fail-closed) | NEWS_PROVIDER_UNAVAILABLE |
| STALE | BLOCKED (fail-closed) | NEWS_DATA_STALE |

Non-CLEAR or critical unknown news state results in unconditional BLOCKED. This is a locked fail-safe rule from docs/MASTER_SPECIFICATION.md.

### 14.2 UNDEFINED Parameters (Open Decisions)

Calendar provider, pre-event window, post-event window, impact threshold, affected currencies: Open Decision #8.
Open position behavior during news: Open Decision #9.

---

## 15. Market Data Interaction

### 15.1 Decision Table by Market Data Status

| market_data_status | New Trade Authorization | Reason Code |
|---|---|---|
| READY | PERMITTED (subject to spread check) | Proceed |
| DEGRADED | BLOCKED | MARKET_DATA_DEGRADED |
| STALE | BLOCKED | MARKET_DATA_STALE |
| RECONNECTING | BLOCKED | MARKET_DATA_RECONNECTING |
| CLOSED | BLOCKED | MARKET_CLOSED |
| UNKNOWN | BLOCKED | MARKET_DATA_UNKNOWN |

### 15.2 Spread Check

IF spread > max_spread_usd THEN BLOCKED (SPREAD_TOO_WIDE).
max_spread_usd: UNDEFINED (Open Decision #10).

### 15.3 Tick Staleness Check

IF (server_received_at - tick_timestamp) > max_tick_staleness_ms THEN treat as STALE.
max_tick_staleness_ms: UNDEFINED (Open Decision #11).

---

## 16. Atomic Authorization

### 16.1 Concurrency Prevention

Concurrent signals are prevented from exceeding risk limits through database-level mutual exclusion during evaluation plus immediate reservation writing.

### 16.2 Mechanism

PostgreSQL row-level lock (SELECT ... FOR UPDATE on account exposure record) during evaluation:
1. Lock account exposure record.
2. Evaluate all risk checks against Effective Exposure (Open + In-Flight).
3. If APPROVED: write AUTHORIZATION_RESERVATION within same transaction.
4. Commit transaction (releases lock).
5. If BLOCKED: rollback or commit without reservation.

Recommendation: PostgreSQL row-locking or serializable transaction. Open Decision #12.

### 16.3 Reservation Lifecycle

  SIGNAL APPROVED -> Write DB reservation -> Counted in Effective Exposure
  -> Released on MT5 FILLED / REJECTED / EXPIRED
  -> Persists in PostgreSQL (survives backend restarts).

---

## 17. Idempotency

- signal_id uniqueness: Same signal_id submitted twice returns cached RiskDecision. No second reservation created.
- Max one signal per account in PENDING_RISK at a time.
- command_id uniqueness: Repeated MT5 dispatch with same command_id returns original execution status.
- Restart recovery: Reconstruct risk state from PostgreSQL (source of truth). Redis is mirror only.
- Unmatched retry without valid command_id: BLOCKED (DUPLICATE_PENDING_SIGNAL).

---

## 18. Fail-Safe Matrix

| Condition | New Trade Entry |
|---|---|
| Risk NOT_CONFIGURED | **NO** |
| Risk NORMAL | **YES** |
| Risk CAUTION | **NO** |
| Risk PROTECTED | **NO** |
| Risk STOPPED | **NO** |
| Risk EMERGENCY_STOP | **NO** |
| emergency_stop_active == True | **NO** |
| Brain NOT_CONFIGURED | **NO** |
| Brain unavailable | **NO** |
| Market data STALE / DEGRADED / RECONNECTING / CLOSED / UNKNOWN | **NO** |
| Spread > max_spread_usd | **NO** |
| News state non-CLEAR (PRE_EVENT, IN_EVENT, POST_EVENT, UNKNOWN, etc.) | **NO** |
| Risk Engine unavailable | **NO** (fail-closed) |
| Duplicate pending signal active | **NO** |
| DAILY_LOSS >= daily_loss_limit_usd | **NO** |
| CURRENT_DRAWDOWN >= max_drawdown_usd | **NO** |
| max_open_positions reached (including in-flight) | **NO** |
| max_open_lots would be exceeded | **NO** |
| Signal expired | **NO** |
| Account state snapshot stale | **NO** |
| Profit-lock floor breached | **NO** |
| Reconciliation inconsistency detected | **NO** (EMERGENCY_STOP) |
| MT5 disconnected | **NO** |
| is_fully_configured == False | **NO** |

---

## 19. Account Normalization

### 19.1 Normalized USD

AUREXIS uses **normalized USD** as authoritative currency for all risk calculations, audit records, and state transitions.

### 19.2 Cent Account Conversion

Cent accounts report values in broker-native units (cents). Conversion:

  USD_value = broker_native_value * cent_normalization_factor

For Cent accounts: cent_normalization_factor = 0.01 (10,000 cents = $100 USD).
For Standard USD accounts: cent_normalization_factor = 1.0.
Implemented via backend/services/normalization.normalize_broker_to_usd() using Decimal arithmetic exclusively.

### 19.3 IDR Display Conversion

USD -> IDR conversion is display-only. Never used in risk calculations, limit comparisons, or authoritative state. Exchange rate: UNDEFINED (Open Decision #13).

### 19.4 Precision Rules

- All monetary values: Decimal with NUMERIC(18,8) in PostgreSQL.
- Risk decisions compare Decimal to Decimal. No float arithmetic in risk paths.
- Display rounding (e.g. 2dp USD, 0dp IDR): applied at presentation layer only.

---

## 20. Auditability

### 20.1 Audit Record Fields

| Field | Description |
|---|---|
| decision_id | UUID of this specific decision |
| signal_id | Signal UUID evaluated (or null) |
| account_id | Account evaluated |
| correlation_id | Distributed trace token |
| decided_at | UTC timestamp |
| decision | APPROVED / BLOCKED / NOT_CONFIGURED / EMERGENCY |
| reason_code | Canonical machine-readable token |
| explanation | Human-readable narrative |
| risk_state | State at decision time |
| config_version | Exact config version applied |
| strategy_version | Brain version that produced the signal |
| evaluated_limits | Map of limits and actual values evaluated |
| equity_at_decision | Decimal USD |
| drawdown_at_decision | Decimal USD |
| daily_pnl_at_decision | Decimal USD |
| authorized_lot_size | Decimal or None |

### 20.2 Requirements

- Every evaluation emits a record whether APPROVED or BLOCKED.
- Stored RiskAuditRecord must contain sufficient data to replay the decision offline.
- Audit records are immutable. No update or delete.
- Secrets are never logged (no JWT tokens, passwords, or API keys in audit records).

---

## 21. Configuration Versioning

- Every RiskConfig carries a config_version string uniquely identifying its parameter set.
- config_version recorded in every RiskDecision and audit record.
- When configuration changes: prior version preserved; new version activated with effective timestamp.
- Rollback: reactivate prior version with audit event.
- Configuration storage model: UNDEFINED (Open Decision #14).

---

## 22. Emergency Stop

### 22.1 Triggers

| Trigger | Source |
|---|---|
| Operator activates emergency_stop_active = True | Manual control |
| Reconciliation failure (server vs broker state mismatch) | Reconciliation engine |
| Risk Engine unhandled exception | Internal error handler |
| Impossible financial values (negative equity, negative lots) | Sanity check |
| Security anomaly | Auth layer |
| MT5 disconnect with unknown position state | MT5 reconciliation |

### 22.2 Behavior

- All evaluations return SignalDecision.EMERGENCY.
- New entries: FORBIDDEN unconditionally.
- Existing positions: Emergency close if reconciliation confirms open positions (Open Decision #15).
- Only emergency close commands may be created.
- System never self-recovers. Recovery requires explicit operator intervention.

---

## 23. Recovery

| State | Recovery Path |
|---|---|
| CAUTION | Auto-recovers to NORMAL when positions and drawdown clear caution band. |
| PROTECTED | Session reset or floor breach -> STOPPED. Reset behavior UNDEFINED (Open Decision #4). |
| STOPPED (Daily Loss only) | Auto-recovers at session boundary if drawdown also clear -> NORMAL. |
| STOPPED (Drawdown) | Remains STOPPED until drawdown falls below limit AND operator acknowledges (Open Decision #16). |
| EMERGENCY_STOP | Explicit operator clear only. Requires audit log entry with justification. No auto-recovery. |
| Backend restart | Reconstruct state from PostgreSQL. Does not default to NORMAL. |
| Redis restart | Re-hydrate from PostgreSQL. Redis is mirror only. |
| MT5 disconnect | market_data_status -> RECONNECTING. Blocked until reconnect + reconciliation. |
| Stale market data | Blocked until fresh tick received. Automatic recovery. |
| News provider outage | Blocked until provider reconnects. Automatic recovery. |

---

## 24. Operator Controls

### 24.1 Available Control

Emergency Stop Toggle: POST /api/v1/risk/kill-switch -- activates emergency_stop_active for account. Requires auth. Logged.

### 24.2 What Operator CANNOT Do

- Bypass Risk Engine evaluation for any new entry.
- Override EMERGENCY_STOP without formal recovery protocol.
- Access another user account controls.
- Set position sizing outside approved config bounds.
- Disable audit logging.

### 24.3 Extended Controls

Per-account manual STOPPED state, per-signal override, manual position close: UNDEFINED (Open Decision #17).

---

## 25. Backtest Consistency

Risk Engine in backtest mode must use exactly the same code as live mode:
- Same state machine, same rules, same thresholds.
- Daily reset mechanics replayed from recorded timestamps.
- No relaxed thresholds in backtest.
- News state replayed from historical archive (source: UNDEFINED, Open Decision #8).
- Same normalize_to_usd().
- All reports carry mandatory disclaimer: "Backtest results are not proof of future profitability."
- Divergence from live behavior in any backtest path is a critical defect.

---

## 26. Multi-Account Isolation

Each account has independent: RiskState, AccountRiskSnapshot, daily loss accumulator, equity_peak (HWM), profit-lock state, and authorization reservations.

Account A risk state change never affects Account B decisions.

Current deployment: 1 account. Architecture isolated by design for scaling to 5+.

Global cross-account portfolio risk: UNDEFINED (Open Decision #18).

---

## 27. Undefined Parameters (Master List)

Every parameter below is UNDEFINED in the current repository. No agent may invent any value. All live trading is blocked until each parameter is explicitly approved by the product owner.

| Parameter | Type | Required For | Default in Code |
|---|---|---|---|
| daily_loss_limit_usd | Decimal | Trading authorization | None (NOT_CONFIGURED) |
| max_drawdown_usd | Decimal | Trading authorization | None (NOT_CONFIGURED) |
| caution_drawdown_pct | Decimal | Caution band entry | None (NOT_CONFIGURED) |
| max_open_positions | int | Position exposure gating | None (NOT_CONFIGURED) |
| default_position_size_lots | Decimal | Trade sizing | None (NOT_CONFIGURED) |
| max_open_lots | Decimal | Lot exposure gating | None (NOT_CONFIGURED) |
| max_spread_usd | Decimal | Spread gating | None (NOT_CONFIGURED) |
| max_tick_staleness_ms | int | Market data staleness gating | None (NOT_CONFIGURED) |
| profit_lock_formula | str | Profit-lock floor calculation | None (NOT_CONFIGURED) |
| profit_lock_threshold_usd | Decimal | Profit-lock activation | None (NOT_CONFIGURED) |
| profit_lock_floor_pct | Decimal | Profit-lock floor ratio | None (NOT_CONFIGURED) |
| risk_per_trade_pct | Decimal | Position sizing | None (NOT_CONFIGURED) |
| risk_per_trade_usd | Decimal | Position sizing (fixed USD) | None (NOT_CONFIGURED) |
| news_pre_event_window_minutes | int | News blackout start | None (NOT_CONFIGURED) |
| news_post_event_window_minutes | int | News blackout end | None (NOT_CONFIGURED) |
| news_provider | str | Economic calendar data feed | None (NOT_CONFIGURED) |
| news_impact_threshold | str | Minimum event impact for blackout | None (NOT_CONFIGURED) |
| daily_reset_timezone | str | Session boundary definition | None (NOT_CONFIGURED) |
| drawdown_reference_mode | str | Drawdown benchmark | None (NOT_CONFIGURED) |

---

## 28. Acceptance Criteria

1. Deterministic Output: Fixed inputs -> identical RiskDecision every run.
2. Fail-Closed Verification: Any required parameter None or critical state UNKNOWN / STALE / DEGRADED -> engine returns NOT_CONFIGURED or BLOCKED -- never APPROVED.
3. Emergency Override: emergency_stop_active == True -> SignalDecision.EMERGENCY regardless of profitability.
4. Monetary Precision: All calculations and comparisons use Decimal. Zero float conversion.
5. Atomic Authorization: Simultaneous signals cannot collectively breach max_open_positions or max_open_lots.
6. Audit Completeness: Every decision produces a complete immutable audit record (section 20.1) with no secrets logged.
7. Backtest Identity: Verified identical decision output between live and backtest execution paths.
8. No Invented Values: Code contains no hard-coded defaults for any parameter in section 27. Missing config returns NOT_CONFIGURED.

---

## 29. Open Decisions (Actionable for Product Owner)

| # | Decision | Options | Impact |
|---|---|---|---|
| 1 | Daily loss session reset timezone | (A) UTC 00:00; (B) Broker Server Time 00:00 | Trading day boundary |
| 2 | Drawdown benchmark reference | (A) Lifetime HWM; (B) Session peak; (C) Initial equity; (D) Peak balance | HWM definition for max_drawdown_usd |
| 3 | Position sizing formula | (A) Fixed lot; (B) Pct equity risk; (C) Fixed USD risk; (D) ATR-scaled | authorized_lot_size calculation |
| 4 | Dynamic profit-lock formula and reset | (A) Pct retrace from peak; (B) Fixed USD retrace; (C) Tiered stages | PROTECTED_FLOOR_USD calculation |
| 5 | Profit-lock equity basis | (A) CURRENT_EQUITY (includes floating); (B) Closed balance only | Floor sensitivity to unrealized PNL |
| 6 | Open position treatment on daily loss stop | (A) Immediate market close all; (B) Allow existing SL/TP to run | Post-STOPPED position handling |
| 7 | Basket closure on profit-lock floor breach | (A) Immediate market close; (B) SL moved to floor price; (C) Partial close | FLOOR_BREACHED handling |
| 8 | News protection configuration | Provider, pre-event window (min), post-event window (min), impact threshold, currencies | News blackout parameters |
| 9 | Open position behavior during news events | (A) Hold with existing SL; (B) Close before event; (C) Move SL to break-even | News event position management |
| 10 | Maximum spread threshold | Decimal USD value for XAUUSD | Spread gating activation |
| 11 | Market data staleness threshold | Integer milliseconds | Stale tick detection |
| 12 | Atomic authorization mechanism | (A) PostgreSQL SELECT FOR UPDATE; (B) Serializable transaction; (C) Redis + PostgreSQL | Concurrency safety architecture |
| 13 | USD/IDR display reference | (A) Fixed configured rate; (B) Live FX feed | IDR display conversion |
| 14 | Risk configuration persistence | (A) PostgreSQL risk_configurations table; (B) Environment variables + CI/CD | Config versioning storage |
| 15 | Emergency stop position handling | (A) Market close all positions; (B) Freeze entries, leave positions with hard SL | Emergency exit behavior |
| 16 | Drawdown stop recovery policy | (A) Auto-resume if equity recovers; (B) Mandatory operator re-authorization | STOPPED drawdown recovery |
| 17 | Extended operator controls scope | Manual position close, lot adjustment, stop triggers | Operator UI capabilities |
| 18 | Global portfolio risk controls | (A) Strictly isolated per-account (current); (B) Cross-account ceiling | Multi-account risk architecture |
