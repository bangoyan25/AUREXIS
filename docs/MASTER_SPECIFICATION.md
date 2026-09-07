# AUREXIS MASTER SPECIFICATION
## Version 1.0 — Source of Truth

> **Status:** LOCKED — 2026-09-06
> **Locked by:** TASK-001 governance pass
> **Product:** AUREXIS
> **Purpose:** Centralized trading intelligence, risk management, monitoring and MT5 execution platform.
>
> This document is the highest-authority specification for the AUREXIS project.
> Changes to locked decisions require a formal change request in `adr/` with explicit user approval.
> Undefined decisions remain UNDEFINED until explicitly approved by the user; no coding agent may invent them.

---

# 0. How to use this document

This document consolidates the approved architectural/product direction discussed before implementation.

It is the highest-level project specification.

### Priority order

1. Explicitly locked decisions in this document and `ai/DO_NOT_CHANGE.md`
2. More detailed approved specifications in `docs/`
3. Approved ADR/change requests
4. Task acceptance criteria
5. Existing code

If code conflicts with a locked requirement, the coding agent must not silently change the requirement.

If a requirement is not defined, it is **UNDEFINED**. The agent must not invent a trading rule, risk rule, API contract, database relationship or broker behavior merely to make implementation easier.

---

# 1. Product identity

## 1.1 Official product name

**AUREXIS**

The previous temporary name is replaced by AUREXIS as the official project/product name.

## 1.2 Product category

AUREXIS is **not merely an EA**.

It is a centralized trading intelligence and risk-management platform in which:

- the website is the control/monitoring interface;
- the server-side Brain performs market analysis;
- the Risk Engine controls whether exposure is permitted;
- the Execution Engine manages commands;
- MT5 acts as the broker-facing execution agent.

## 1.3 Product philosophy

AUREXIS is **risk-first**.

The project does not promise a daily profit, a win rate, or a specific return.

A target such as $10/day is an optional objective/measurement, not a reason to increase risk or force trades.

---

# 2. Initial trading scope

## 2.1 Broker

Initial broker target:

**HFM**

The first implementation/testing environment may use an HFM Cent account.

## 2.2 Account

Initial development/testing:

**One trading account.**

The architecture must be designed so that it can scale to:

**5 accounts or more.**

Multi-account capability must include strict account isolation.

## 2.3 Instrument

Initial and current strategy scope:

**XAUUSD only**

The canonical platform symbol is `XAUUSD`.

Broker-specific symbol names must be mapped explicitly.

## 2.4 Market analysis

Target:

**Tick-by-tick analysis.**

The platform must distinguish between:

- market observation;
- normalized market state;
- signal generation;
- risk approval;
- execution.

---

# 3. Core architecture

## 3.1 Centralized Brain

The Brain lives on the server, not inside MT5.

High-level flow:

```text
Market Data
    ↓
Normalization
    ↓
Market State
    ↓
Trading Brain
    ↓
Candidate Signal
    ↓
Risk Engine
    ↓
Approved / Rejected
    ↓
Execution Command
    ↓
MT5 EA
    ↓
Broker / HFM
    ↓
Execution Result
    ↓
Reconciliation
    ↓
Database
    ↓
Dashboard / Realtime Events
```

## 3.2 MT5 role

MT5 is an execution agent.

The EA may:

- connect/authenticate;
- maintain heartbeat;
- receive valid server commands;
- validate commands;
- execute orders;
- modify/close positions when commanded;
- report account state;
- report positions/orders/trades;
- report execution results;
- report errors/connectivity;
- participate in reconciliation.

The EA must not:

- invent signals;
- invent strategy rules;
- bypass the Risk Engine;
- arbitrarily increase volume;
- open new trades without a valid command;
- silently implement a second trading strategy.

---

# 4. Trading intelligence

## 4.1 Intended strategy concepts

The approved strategic direction combines multiple forms of market evidence:

- follow-the-trend;
- market structure;
- breakout;
- fakeout;
- multiple indicators as confirmation;
- volatility/context;
- news protection.

## 4.2 Market structure

The Brain should understand market structure rather than relying on a single indicator.

Exact algorithmic definitions of:

- swing highs;
- swing lows;
- higher highs;
- higher lows;
- lower highs;
- lower lows;
- break of structure;
- change of character;
- liquidity events;

remain subject to final strategy specification.

## 4.3 Trend

The system should classify trend/context before considering an entry.

Trend classification may use price structure and approved indicators.

Exact periods and thresholds are **UNDEFINED** until explicitly locked.

## 4.4 Breakout

Breakout detection is an approved strategy component.

The implementation must define what constitutes:

- valid range;
- breakout;
- confirmation;
- failed breakout;
- retest;
- invalidation.

Do not invent these definitions without approval.

## 4.5 Fakeout

Fakeout detection is an approved component.

The system should distinguish genuine breakout continuation from failed breakout/reversal conditions.

Exact algorithm remains **UNDEFINED**.

## 4.6 Indicators

The concept allows multiple indicators for confirmation.

Indicators discussed as candidates include:

- EMA;
- ADX;
- ATR;
- RSI;
- volume where reliable.

However:

> Indicator names do not constitute final rules.

Exact:

- period;
- threshold;
- timeframe;
- weighting;
- interaction;
- confirmation requirement;

must be explicitly approved before production implementation.

## 4.7 Signal confidence

A signal may have a confidence/quality score.

The confidence system must not become an excuse to invent arbitrary trade rules.

Exact scoring formula and minimum threshold are **UNDEFINED**.

---

# 5. Trading command philosophy

AUREXIS should not operate as:

```text
Daily target reached → stop forever
```

Instead:

```text
Valid opportunity
+
Risk approval
=
Trade may continue
```

A profit milestone does not automatically terminate the trading session.

The dynamic protection mechanism determines when trading must stop.

---

# 6. Risk Engine

## 6.1 Highest priority

Risk management has higher authority than signal generation.

A strong signal cannot override a blocked risk state.

## 6.2 Required controls

The Risk Engine must support:

- account risk state;
- daily loss protection;
- equity-based protection;
- dynamic profit lock;
- position sizing;
- exposure limits;
- spread/market-condition protection;
- news protection;
- account kill switch;
- global kill switch;
- stale-data protection;
- execution/reconciliation protection.

## 6.3 Dynamic profit lock

The approved concept is a **rising protection level based on the account's equity peak/profit progress**.

Illustrative approved examples:

```text
Profit reaches +$10
→ continue trading
→ protection may be around -$3

Profit reaches +$20
→ protection moves higher
→ protection may be around -$6
```

The principle is:

> As protected profit increases, the amount of allowable giveback increases in a controlled and predefined manner.

These examples are **conceptual reference points**, not a final mathematical formula.

The final formula must define:

1. starting/reference equity;
2. peak equity;
3. protected equity;
4. protection distance;
5. step/continuous behavior;
6. reset behavior;
7. day/session boundary;
8. deposit/withdrawal handling;
9. open-position behavior after stop;
10. precision/rounding;
11. cent-account normalization;
12. edge cases.

Until those are approved, the implementation must not hard-code the examples as universal production rules.

## 6.4 Daily risk protection

The system must be able to stop opening new positions when the configured daily risk limit is reached.

The exact final percentage/value configuration must be explicitly approved.

The earlier concept of a daily stop such as 10% is a risk-policy example, not permission for the coding agent to choose arbitrary limits.

## 6.5 Risk-first behavior

The system must never increase risk simply because:

- the account is below a target;
- the day is negative;
- a previous trade lost;
- the model has high confidence;
- the user wants to reach a profit target.

No revenge trading.

No implicit martingale.

No uncontrolled averaging.

---

# 7. Account and money normalization

## 7.1 Cent accounts

When an HFM Cent account is used, broker-native cent values must be normalized for the AUREXIS user interface and risk calculations.

Example concept:

```text
Broker-native:
10,000 cents

AUREXIS display:
$100
```

The user should be able to read PNL in normal USD terms rather than having to mentally convert cents.

## 7.2 PNL

The platform should display:

- balance;
- equity;
- realized PNL;
- unrealized PNL;
- daily PNL;
- session PNL;
- account PNL.

The currency representation must be clearly labeled.

## 7.3 IDR conversion

AUREXIS should support an optional USD → IDR presentation.

Example:

```text
PNL:
+$200 USD

≈ Rp xxx.xxx
```

The IDR amount must be calculated using the applicable exchange rate for the selected timestamp/source.

The system must not present a stale or unexplained conversion as if it were an exact live broker value.

---

# 8. News protection

## 8.1 Objective

Avoid unnecessary exposure to extreme volatility surrounding major economic news.

## 8.2 Behavior

AUREXIS should support configurable:

```text
Pre-news block
+
Post-news block
```

during selected high-impact events.

## 8.3 Important distinction

News protection is a **risk control**, not a trading signal.

## 8.4 Undefined

Before production:

- calendar provider;
- event reliability;
- impact mapping;
- currency relevance;
- pre-event duration;
- post-event duration;
- behavior with existing positions;
- fail-safe behavior when calendar data is unavailable;

must be finalized.

---

# 9. Execution Engine

## 9.1 Command lifecycle

```text
CREATED
→ SENT
→ ACKNOWLEDGED
→ EXECUTING
→ FILLED
→ RECONCILED
```

Alternative terminal paths:

```text
PARTIALLY_FILLED → RECONCILED
REJECTED         → RECONCILED
EXPIRED          → RECONCILED
```

Every command must reach a RECONCILED state confirming server-side state matches broker-side state.
The exact reconciliation trigger and timeout are governed by `docs/EXECUTION_ENGINE.md`.

## 9.2 Command identity

Every command requires a unique command ID.

Repeated delivery must not unintentionally duplicate an order.

## 9.3 Command context

A production command should carry enough context to make execution deterministic, including where appropriate:

- command ID;
- account ID;
- canonical symbol;
- broker symbol mapping;
- direction;
- volume;
- SL/TP;
- creation time;
- expiry;
- strategy version;
- risk snapshot/version;
- authentication/signature.

## 9.4 Unknown execution state

Never blindly retry an order if execution status is unknown.

Reconcile first.

---

# 10. Failure-safe behavior

For **new entries**, the default must be:

> If critical information is unknown or stale, do not open a new trade.

Examples:

- market data stale;
- Risk Engine unavailable;
- account state inconsistent;
- MT5 disconnected;
- command authentication invalid;
- reconciliation pending;
- critical database state unavailable.

Existing-position management must be explicitly specified rather than inferred.

---

# 11. Dashboard

The website should provide:

## 11.1 Account overview

- account selector;
- broker;
- account status;
- balance;
- equity;
- normalized USD PNL;
- IDR display;
- drawdown;
- current risk state.

## 11.2 Positions

- symbol;
- side;
- volume;
- entry;
- current price;
- SL;
- TP;
- floating PNL;
- duration;
- account.

## 11.3 Trades

- historical trades;
- entry/exit;
- PNL;
- reason/setup where available;
- strategy version;
- timestamps.

## 11.4 Trading calendar / PNL calendar

The user can select an account and inspect daily performance:

```text
Account 1

1 Sep   +$12
2 Sep   -$3
3 Sep   +$7
4 Sep   +$21
...
```

The calendar must support account filtering and date navigation.

## 11.5 Risk visualization

Show:

- current equity;
- equity peak;
- current protected level;
- current drawdown;
- daily risk state;
- trading enabled/disabled;
- reason for a stop/block.

---

# 12. Multi-account architecture

The first test uses one account.

The architecture must support:

```text
Account 1
Account 2
Account 3
...
Account N
```

Each account has isolated:

- credentials/agent identity;
- positions;
- trades;
- PNL;
- risk state;
- commands;
- reconciliation state.

A signal/command for Account 1 must never accidentally execute against Account 2.

---

# 13. Data architecture

## Durable source of truth

PostgreSQL.

## Realtime/cache/streaming support

Redis.

## Planned entities

- users;
- accounts;
- brokers;
- MT5 agents;
- strategies;
- strategy versions;
- signals;
- commands;
- orders;
- positions;
- trades;
- risk states;
- equity snapshots;
- daily PNL;
- market ticks;
- news events;
- audit logs;
- system events.

Exact schema is governed by `docs/DATABASE_SCHEMA.md`.

---

# 14. Realtime architecture

The dashboard should receive realtime events through a server-controlled realtime layer.

Candidate event categories:

- ACCOUNT_UPDATED;
- POSITION_OPENED;
- POSITION_CLOSED;
- PNL_UPDATED;
- SIGNAL_CREATED;
- COMMAND_CREATED;
- COMMAND_SENT;
- COMMAND_FILLED;
- RISK_STATE_CHANGED;
- MT5_CONNECTED;
- MT5_DISCONNECTED.

Exact payload contracts are governed by `contracts/` and `docs/WEBSOCKET_SPEC.md`.

---

# 15. Security

## Never store in Git

- passwords;
- private keys;
- API keys;
- broker passwords;
- JWT secrets;
- encryption keys;
- production tokens.

Use:

```text
.env
```

locally, ignored by Git.

Use:

```text
.env.example
```

for placeholders only.

Production should use dedicated secret management when practical.

## Trading credentials

Prefer keeping broker credentials within the MT5 execution environment rather than exposing plaintext broker passwords to the Brain.

## AI security

Never paste production credentials into an AI coding prompt.

---

# 16. Infrastructure

## Initial logical topology

```text
                Internet
                   │
                   ▼
             Reverse Proxy
                   │
          ┌────────┴────────┐
          ▼                 ▼
      Frontend          Backend/API
                            │
                  ┌─────────┼─────────┐
                  ▼         ▼         ▼
                Brain      Risk    Execution
                  │         │         │
                  └─────────┼─────────┘
                            │
                    PostgreSQL / Redis
                            │
                            ▼
                       MT5 Agent
                            │
                            ▼
                           HFM
```

## Suggested separation

Linux VPS:
- frontend;
- backend;
- Brain;
- Risk Engine;
- Execution Engine;
- PostgreSQL;
- Redis;
- reverse proxy.

Windows VPS:
- MT5 terminal;
- AUREXIS MT5 EA.

Start with one account and scale after reliability is proven.

---

# 17. Latency philosophy

A low-latency VPS can materially improve execution responsiveness, but:

> low latency does not make a weak strategy profitable.

Latency optimization is valuable for:

- market-data freshness;
- command delivery;
- order execution;
- reconciliation.

It must not be used as a substitute for:

- sound risk management;
- robust strategy validation;
- realistic backtesting;
- execution safeguards.

Exact target latency budgets are **UNDEFINED** until measured in the target broker environment.

---

# 18. Backtesting

Backtests must model realistic execution as far as data permits.

Consider:

- tick data;
- bid/ask;
- spread;
- slippage;
- latency;
- commission;
- swap;
- trading sessions;
- news protection;
- broker symbol specifications.

Validation should include:

- in-sample;
- out-of-sample;
- walk-forward;
- parameter sensitivity;
- stress testing;
- Monte Carlo where appropriate.

No backtest is proof of future profitability.

---

# 19. Observability

Production monitoring should include:

- API health;
- Brain health;
- Risk Engine health;
- PostgreSQL health;
- Redis health;
- MT5 heartbeat;
- market-data freshness;
- command latency;
- command failures;
- execution rejections;
- reconciliation mismatches;
- risk-state changes;
- system errors.

Important trading events must be auditable.

---

# 20. AI coding governance

The coding agent is an implementation assistant, not the product owner.

The agent must:

1. Read the relevant specification before coding.
2. Respect locked decisions.
3. Never invent undefined trading behavior.
4. Never move Brain logic into MT5.
5. Never bypass Risk Engine.
6. Never hard-code secrets.
7. Never silently change contracts.
8. Never delete tests to make them pass.
9. Make small, reviewable changes.
10. Run relevant tests.
11. Report assumptions and limitations.
12. Raise a change request when architecture or locked behavior must change.

---

# 21. Development workflow

```text
SPEC
 ↓
TASK
 ↓
PLAN
 ↓
IMPLEMENT
 ↓
TEST
 ↓
VERIFY
 ↓
REVIEW
 ↓
MERGE
```

For architectural changes:

```text
PROPOSAL
 ↓
CHANGE REQUEST / ADR
 ↓
USER APPROVAL
 ↓
SPEC UPDATE
 ↓
IMPLEMENTATION
```

---

# 22. What is locked vs undefined

## Locked

- AUREXIS is the product name.
- Centralized Brain architecture.
- MT5 is execution-only.
- HFM is initial broker target.
- HFM Cent account may be used for testing.
- Start with one account.
- Architecture must scale to 5+ accounts.
- XAUUSD is the initial/only instrument.
- Tick-by-tick analysis is the target.
- Risk-first philosophy.
- Profit target is not the primary objective.
- Dynamic profit-lock concept.
- News protection concept.
- Account-level PNL calendar.
- USD normalization for Cent account presentation.
- USD → IDR display conversion.
- Risk Engine has authority over new-trade approval.
- Critical unknown state defaults to no new entry.
- Documentation is the source of truth.
- Secrets do not belong in project documentation/Git.

## Still UNDEFINED and must not be invented

- exact strategy formulas;
- exact indicator periods;
- exact indicator thresholds;
- exact signal scoring;
- exact confidence threshold;
- exact market-structure algorithm;
- exact breakout/fakeout algorithm;
- exact SL algorithm;
- exact TP algorithm;
- exact position-sizing formula;
- exact maximum exposure;
- exact daily risk percentage/value;
- generalized dynamic profit-lock formula;
- news provider;
- exact pre/post news windows;
- market data staleness threshold (maximum acceptable tick age before blocking new entries);
- tick data retention policy (hot state duration, analytics retention, historical storage);
- exact latency budget;
- exact production infrastructure sizing;
- final database columns;
- final API schemas;
- final WebSocket payloads.

---

# 23. Definition of Done for production trading

AUREXIS must not be considered live-ready merely because the UI works or the EA can place an order.

Before live trading, the system should demonstrate:

- specification completeness;
- tested risk engine;
- tested command idempotency;
- MT5 disconnect handling;
- reconciliation;
- account isolation;
- realistic backtesting;
- failure testing;
- audit logging;
- backup/recovery;
- monitoring;
- secret management;
- demo/forward validation;
- manual emergency controls.

---

# 24. Final principle

AUREXIS should be engineered as a **risk-controlled trading system**, not a profit-generation promise.

The system's order of priority is:

```text
1. Capital protection
2. Correct market analysis
3. Correct risk decision
4. Reliable execution
5. Accurate state/reconciliation
6. Observability
7. Profit optimization
```

If maximizing profit conflicts with preserving a locked risk rule:

> **The risk rule wins.**

---

# 25. Current status

**Specification locked.**

`docs/MASTER_SPECIFICATION.md` v1.0 was formally locked on 2026-09-06 by TASK-001.

The next implementation step is not to build a complete trading strategy in one shot.

The correct next step is to finalize the remaining undefined decisions (TASK-002 through TASK-007) before implementing trading or risk logic. Foundation infrastructure tasks (TASK-101 through TASK-106) may proceed in parallel with strategy specification where they do not depend on undefined trading parameters.

Remaining undefined decisions requiring explicit user approval before implementation:

1. generalized dynamic profit-lock formula (TASK-002);
2. exact risk limits and daily protection (TASK-002);
3. exact market-structure/trend/breakout/fakeout definitions (TASK-003);
4. signal scoring and confidence threshold (TASK-003);
5. execution command contract finalization (TASK-004);
6. database schema finalization (TASK-005);
7. API/WebSocket contracts finalization (TASK-006, TASK-007).

Only after these are approved should production trading logic be implemented.
