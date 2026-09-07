# AUREXIS Execution Engine

## Responsibilities

- receive approved trade intent
- validate account and symbol
- create unique command
- attach risk snapshot/version
- send to MT5
- track acknowledgement
- track broker execution
- handle rejection/timeout
- reconcile
- publish execution state

## Command lifecycle

CREATED
-> SENT
-> ACKNOWLEDGED
-> EXECUTING
-> FILLED / PARTIALLY_FILLED / REJECTED / EXPIRED
-> RECONCILED

## Safety

- unique command ID
- expiry
- account binding
- symbol binding
- server timestamp
- strategy version
- risk snapshot
- authentication/signature
- duplicate protection

Never retry a trade command blindly if the broker execution state is unknown. Reconcile first.
