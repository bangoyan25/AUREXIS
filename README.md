# AUREXIS

AUREXIS is a centralized trading intelligence and risk-management platform with MT5 as the execution layer.

## Core architectural principle

The website/server is the Brain. MT5 is an execution agent.

The MT5 EA must not independently invent trading decisions or bypass the server-side risk engine.

## Current scope

- Broker: HFM (initial target)
- Account model: HFM Cent for testing
- Instrument: XAUUSD
- Initial deployment: 1 account
- Architecture target: scalable to 5+ accounts
- Market analysis target: tick-by-tick
- Dashboard: account, equity, balance, PNL, positions, trades, risk state and calendar
- Currency presentation: normalized USD, with optional IDR conversion for display
- Risk-first philosophy: profit targets are secondary to capital preservation

## Source of truth

Before changing code, read:

1. `ai/AI_RULES.md`
2. `ai/DO_NOT_CHANGE.md`
3. `docs/SYSTEM_SPEC.md`
4. `docs/ARCHITECTURE.md`
5. the relevant specification for the task
6. `ai/TASKS.md`

If code and a locked specification conflict, do not silently change the specification. Raise a change request.

## Security

Never commit `.env`, credentials, private keys, broker passwords, API keys, or production secrets.

## Master specification

Read `docs/MASTER_SPECIFICATION.md` as the highest-level consolidated source of truth before implementation.
