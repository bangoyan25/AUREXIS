# AUREXIS News Protection

## Objective

Reduce exposure to extreme volatility around major economic events.

## Intended behavior

A configurable no-new-entry window:
- before selected high-impact news
- after selected high-impact news

## Required design decisions

- calendar provider
- event source reliability
- impact classification
- affected currencies
- timezone normalization
- pre-event window
- post-event window
- behavior with open positions
- fail-closed behavior when calendar data is stale/unavailable

News protection is a risk control, not a signal generator.
