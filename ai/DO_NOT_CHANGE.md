# AUREXIS Locked / Protected Decisions

These decisions are protected from silent modification.

## Locked

- Product name: AUREXIS
- Centralized Brain architecture
- MT5 is execution-only
- Risk Engine has authority over new-trade approval
- XAUUSD is the initial/only trading instrument
- HFM is the initial broker target
- Start testing with one account
- Architecture must be scalable to 5+ accounts
- Tick-by-tick analysis target
- Risk-first philosophy
- Cent-account values are normalized/presented as USD for user-facing PNL
- Optional USD -> IDR display conversion
- News protection is part of risk management
- Fail-safe: critical unknown/stale state means no new entries
- Repository documentation is the source of truth for coding agents
- Secrets must not be stored in repository documentation

## Protected but not fully parameterized

The dynamic profit-lock concept is approved, but the generalized formula and edge cases still require a final specification before production coding.

## Change rule

A coding agent must not alter a protected decision silently. Create a change request in `adr/` and wait for explicit approval.
