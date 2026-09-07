# AUREXIS Market Data Specification

## Initial instrument

Canonical symbol: `XAUUSD`

## Tick fields

At minimum:
- bid
- ask
- timestamp
- symbol
- broker symbol

Additional fields may include spread and volume where reliably available.

## Normalization

Broker-specific symbols map to a canonical instrument.

## Staleness

The system must define a maximum acceptable age for market data before allowing a new entry. Until approved, treat the threshold as UNDEFINED.

## Storage

Do not automatically store every tick permanently without a retention/performance decision. Define hot state, analytics retention and historical storage separately.
