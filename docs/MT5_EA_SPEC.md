# AUREXIS MT5 EA Specification

## Role

MT5 EA is an execution agent, not the trading Brain.

## EA responsibilities

- authenticate/connect
- maintain heartbeat
- receive server commands
- validate command format and account binding
- execute approved orders
- modify/close positions when commanded
- report order/position/account events
- report connectivity and errors
- reconcile local/broker state with server state

## EA must NOT

- invent trading signals
- bypass Risk Engine
- change approved risk parameters
- arbitrarily change volume
- open a new trade without a valid server command
- silently implement a second strategy

## Broker symbol mapping

The platform uses canonical `XAUUSD`; broker-specific symbol names must be mapped explicitly.

## Failure behavior

On server communication failure, do not create new entries from locally invented logic. Reconnection must include state reconciliation.
