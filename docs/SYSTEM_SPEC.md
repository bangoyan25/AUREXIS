# AUREXIS System Specification

## 1. System boundary

Browser -> Web App -> API/Realtime -> Brain/Risk/Execution services -> MT5 Agent -> HFM

## 2. Authority model

1. Market data provides observations.
2. Brain evaluates market context and creates candidate signals.
3. Risk Engine has authority to approve/reject exposure.
4. Command Engine creates an execution command only after risk approval.
5. MT5 validates and executes a valid command.
6. Execution results return to the server.
7. Server reconciles its state against broker/MT5 state.

## 3. Fail-safe rule

When critical state is unknown or stale, the default for NEW entries is NO NEW TRADE.

Examples:
- market data stale
- risk state unavailable
- account state inconsistent
- MT5 disconnected
- command authenticity invalid
- reconciliation pending

Existing-position emergency handling must be explicitly specified; do not infer it from the no-new-entry rule.

## 4. Idempotency

Every execution command must have a unique command ID. Repeated delivery of the same command must not create an unintended duplicate trade.

## 5. Auditability

Important state transitions must be persisted, including signal creation, risk approval/rejection, command creation/sending/receipt, order execution, position changes, risk-state changes and system errors.

## 6. Time

Persist timestamps in UTC. Convert to the user's display timezone only at presentation time.

## 7. Money

Use a precise monetary representation for financial calculations. Broker-native cent-account values must be normalized into the platform's USD abstraction layer for risk and PNL presentation.

## 8. Unknowns

Any requirement not explicitly approved is `UNDEFINED`, not an invitation for the coding agent to invent behavior.
