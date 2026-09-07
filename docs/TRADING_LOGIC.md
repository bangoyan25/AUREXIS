# AUREXIS Trading Logic Specification

## Objective

Build a mature XAUUSD decision engine focused on market context, risk control and high-quality setups rather than maximizing trade frequency or promising profit.

## Intended evidence categories

The approved concept includes:
- follow-the-trend
- market structure
- breakout
- fakeout
- multiple indicators as confirmation
- volatility/context
- news protection

Potential indicators mentioned in the engineering discussion include EMA, ADX, ATR, RSI and volume. Their exact periods, thresholds, weighting and role are NOT locked here unless explicitly approved.

## Important rule

Indicators are evidence, not automatic buy/sell triggers.

Do not implement:
EMA cross + RSI + MACD = BUY
unless that exact rule is separately approved.

## Signal pipeline

Market context
-> structure classification
-> trend classification
-> setup detection
-> confirmation
-> signal confidence
-> risk pre-check
-> candidate trade

The exact scoring model, entry criteria, stop placement, take-profit logic and exit rules must be finalized before production trading.

## Undefined items

- exact indicator parameters
- exact confidence threshold
- exact market-structure algorithm
- breakout/fakeout definitions
- stop placement algorithm
- take-profit algorithm
- position-sizing formula
- maximum simultaneous exposure
