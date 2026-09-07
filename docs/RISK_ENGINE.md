# AUREXIS Risk Engine Specification

## Principle

Risk Engine is authoritative over trade approval.

No new trade may bypass it.

## Required controls

- account-level risk state
- daily loss protection
- equity-based protection
- dynamic profit lock
- position sizing
- exposure limits
- spread/market-condition protection
- news protection
- emergency/global kill switch
- account-level stop
- stale-data protection
- reconciliation protection

## Dynamic profit protection

The design discussed uses a rising protection level based on equity peaks.

Illustrative approved examples:
- peak profit +$10 -> protection at -$3
- peak profit +$20 -> protection at -$6

These examples establish the concept, not necessarily the final mathematical formula.

Before coding, define:
1. reference equity
2. peak equity calculation
3. protected-profit formula
4. reset conditions
5. daily/session boundaries
6. behavior after a stop
7. whether existing positions may be managed/closed after stop
8. rounding/precision
9. handling deposits/withdrawals/credits
10. broker-native cent-account normalization

## Hard safety rule

If required risk state is unknown, reject new entries.

## No profit guarantee

The system must never use a daily profit target as a reason to increase risk.
