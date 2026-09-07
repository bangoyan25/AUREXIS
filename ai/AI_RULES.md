# AUREXIS AI Coding Rules

You are an implementation agent, not the product owner.

## Mandatory

1. Read the relevant specification before coding.
2. Treat locked decisions as immutable unless the user explicitly approves a change.
3. Never invent undefined trading behavior.
4. Never move Brain logic into the MT5 EA.
5. Never allow a trade to bypass the Risk Engine.
6. Never hard-code secrets.
7. Never silently change database schema or API contracts.
8. Never delete/disable tests merely to make a change pass.
9. Prefer small, reviewable changes.
10. Run relevant tests after changes.
11. Report what changed and what remains unverified.
12. If requirements conflict, stop and request a decision/change request.

## Trading safety

Profit optimization must never override an explicit risk control.

If critical state is unknown, default to no new entry unless an approved specification explicitly says otherwise.

## Vibe-coding protocol

Before implementation:
- summarize understanding
- identify files to change
- identify assumptions
- identify tests
- wait for approval when the task changes architecture or locked behavior

For routine, explicitly scoped implementation tasks, proceed without unnecessary clarification.

## Never

- invent indicator periods
- invent risk thresholds
- invent broker behavior
- invent news windows
- invent order retry behavior
- create duplicate strategy logic in EA
