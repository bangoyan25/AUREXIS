# AUREXIS Backtest Specification

> **Status:** DRAFT — 2026-09-06
> **Replaces:** `docs/BACKTEST_SPEC.md` (original stub)
> **Authority:** `docs/MASTER_SPECIFICATION.md` v1.0 (LOCKED)
> **All configurable values: UNDEFINED unless stated.**

---

## 1. Core Rules

1. Backtest Brain uses **exactly the same code** as live Brain — no separate backtest strategy
2. No future information at any decision point
3. Spread, slippage, commission modeled realistically
4. Fills are not guaranteed; rejections possible
5. Risk Engine runs identically (same rules, thresholds)
6. News windows applied using replayed timestamps
7. Results not proof of future profitability

---

## 2. Input Data

Preferred: raw tick data (bid/ask/timestamp/symbol/volume optional).
Minimum: OHLCV bars (limitations: entry imprecision; spread modeled not observed — must be disclosed).

Data quality: gaps, duplicates, out-of-order ticks handled identically to live pipeline.
Historical bar minimum lookback for warm-up: CONFIGURABLE — UNDEFINED.

---

## 3. Replay Rules

**Temporal integrity (absolute):** At replay moment T, Brain accesses only data with timestamp ≤ T.

Bar formation: bars form from ticks exactly as in live mode.
Bar-close calculations trigger only when replay clock passes bar's close time.
No pre-computation of full-dataset indicator series.

Session gaps (weekend, holiday) preserved. No artificial tick injection.
First tick after gap triggers same reconnect/warm-up logic as live.

---

## 4. Indicator Updates

- Tick-level: updated on every replayed tick
- Bar-level: updated on bar close only (same as live)
- No pre-computation across full dataset before replay

Zero look-ahead contamination.

---

## 5. Simulated Execution

BUY fill: `ask` of first tick after signal forwarded.
SELL fill: `bid` of first tick after signal forwarded.
Slippage: additional CONFIGURABLE slippage — UNDEFINED.
Spread at fill: spread of fill tick, not signal tick.
Spread rejection: if spread > limit at fill time → simulate rejection.
Partial fill: not modeled in Phase 1.

SL/TP hit:
- SL BUY: bid ≤ SL → fill at SL (or first tick beyond if gap)
- TP BUY: ask ≥ TP → fill at TP
- Gap: fill at first available bid/ask beyond level.

Commission: Broker Cent XAUUSD rate — UNDEFINED. Applied per-lot at entry and exit.
Swap: Broker XAUUSD overnight rates — UNDEFINED. Applied at daily rollover.

---

## 6. News Replay

Events replayed from recorded timestamps. Pre/post windows: UNDEFINED.
News backtest data source: UNDEFINED.
If news data unavailable for a period: treat as UNKNOWN → no new entries (conservative fail-safe).

---

## 7. Risk Engine in Backtest

Runs identically: same rules, thresholds, daily reset logic. No relaxation.
Daily P&L, peak equity, drawdown tracked on simulated account state.

---

## 8. Account Normalization

Cent (SC) → USD: same `normalize_to_usd()` as live.
USD → IDR: display-only. Exchange rate: fixed reference or UNDEFINED.

---

## 9. Required Metrics

Total net P&L (USD, after commission+swap) | Win rate | Avg R achieved vs planned |
Max drawdown (USD + %) | Profit factor | Trade count | Avg trade duration |
Sharpe-class metric (formula: UNDEFINED) | Calmar-class metric (formula: UNDEFINED) |
News-blocked signal count | Risk-rejected count | Signal expiry rate | Spread-rejected count.

Every report discloses: data range; warm-up excluded from stats; spread model; slippage assumptions; commission rates; known gaps.

**"Backtest results are not proof of future profitability."** — mandatory disclaimer in every report.

---

## 10. Overfitting Protection

Walk-forward required: in-sample parameter exploration → out-of-sample validation (never reused).
Multiple walk-forward steps with non-overlapping out-of-sample windows.

Parameter sensitivity: parameters must be stable at adjacent values.
N=14 optimal but N=13 or N=15 drastically worse → likely overfit → reject.

Multiple testing bias: final parameter set tested exactly once on clean out-of-sample dataset.

---

## 11. Reproducibility

Identical results given identical: tick data file (hash recorded) + strategy version +
all config + Risk Engine config + news data file (hash) + random seed.

Run record: `run_id`, `timestamp`, config snapshot, `strategy_version`, data hashes.

---

## 12. Divergence Prevention

| Concern | Mitigation |
|---------|-----------|
| Different code in backtest | Same module, no backtest-mode branching |
| Different indicator init | Same warm-up, same bar count |
| Relaxed Risk Engine | Same rules, no relaxation |
| Optimistic spread | Actual or representative spread |
| Unrealistic fills | Actual bid/ask + slippage |
| Missing news | UNKNOWN → conservative |
| Different normalization | Same `normalize_to_usd()` |
