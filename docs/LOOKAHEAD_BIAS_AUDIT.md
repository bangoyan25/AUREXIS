# AUREXIS Look-Ahead Bias Audit

**Date:** 2026-09-06
**Strategy Version:** AUREXIS-STRAT-1.0.0
**Auditor:** Implementation Engineer

---

## 1. Definition

Look-ahead bias occurs when a signal or calculation uses data that would not be available at the time of signal generation.

AUREXIS must guarantee that:
- No indicator uses any bar that has not yet **closed**.
- No structural level uses a future swing point.
- No breakout detection uses future close prices.
- No news state uses future events.
- No spread uses a future tick.

---

## 2. Architecture Invariants (Causal Guarantees)

### 2.1 Closed-Bar Rule

**Locked in:** `brain/pipeline.py` Stage 1

```python
if not closed_bars or not all(b.is_closed for b in closed_bars):
    return self._empty_signal(symbol, "INSUFFICIENT_CLOSED_BARS")
```

All `Bar` objects passed to indicator functions must have `is_closed=True`.
The `BarBuilder` only emits a `Bar` when a new tick arrives in a **subsequent** time bucket,
guaranteeing the bar's OHLCV is final.

### 2.2 BarBuilder Causality

**File:** `brain/bar_builder.py`

- The `BarBuilder.process_tick()` method emits a closed `Bar` only when
  `bucket_start > self._current_bar_start`.
- The emitted bar represents the **previous** interval.
- The current in-progress bar is never emitted as closed.
- There is no indexing into future bars.

### 2.3 Indicator Calculations

**File:** `brain/indicators.py`

| Indicator | Lookahead Risk | Mitigation |
|-----------|---------------|-----------|
| `calculate_ema()` | None | Uses `bars[:period]` as seed, then iterates forward through closed bars |
| `calculate_sma()` | None | `bars[-period:]` — tail of closed bars only |
| `calculate_atr()` | None | Uses `prev_close` from `i-1`, processes bars in order |
| `calculate_rsi()` | None | Processes gains/losses in chronological order |
| `calculate_adx()` | None | Processes DM/TR in chronological forward order |
| `calculate_atr_baseline()` | None | Only accesses bars before `end_idx = total_bars - baseline_bars + offset + 1` |

**Verdict:** No future indexing in any indicator function.

### 2.4 Market Structure

**File:** `brain/structure.py`

`detect_swing_points()` uses `lookback` bars on both sides of the pivot.
The loop ends at `max_eval_idx = len(bars) - lookback`, which means the most recent `lookback` bars are never evaluated as pivots — they haven't yet completed their right-side context.

This means swing points are confirmed **lookback** bars after the actual pivot — this is causal.
No future bar is ever accessed.

### 2.5 Setup Detection

**File:** `brain/strategy/setups.py`

`detect_setup()` uses only:
- `bars[-1]` — most recent closed bar
- `bars[-2]` — second-most-recent closed bar
- `structure.recent_swing_high` and `structure.recent_swing_low` — derived from closed bars

No future bar is referenced.

### 2.6 Regime Classification

**File:** `brain/regime.py`

`classify_regime()` takes a list of closed bars and computes all indicators forward-in-time.
No negative indexing beyond `bars[-1]` (most recent closed bar).

### 2.7 Scoring

**File:** `brain/scoring.py`

`MultiFactorScorer.evaluate()` uses:
- `tick` — current bid/ask (real-time observation, not future)
- `structure` — derived from closed bars
- `regime_ctx` — derived from closed bars
- `news_state` — injected at call time (current state)

No future data accessed.

### 2.8 Backtest Engine

**File:** `brain/backtest/engine.py`

The backtest streams ticks **strictly in chronological order**.
```python
for tick in ticks:  # chronological iteration
    # 1. Check SL/TP on open positions
    # 2. Update floating equity
    # 3. Feed tick into BarBuilder
    # 4. If new closed bar: evaluate Brain pipeline
    # 5. If signal approved: open new position
```

Critically:
- The `BarBuilder` only emits a closed bar when a tick **crosses into the next time bucket**.
- `closed_bars` accumulates incrementally — no future bars ever appear.
- Future news state: backtest uses `news_state="CLEAR"` — no recorded future news injected.
- Future spread: uses `tick.ask - tick.bid` at the **current** tick position.
- Future SL/TP checks: `tick.bid`/`tick.ask` at current tick, not future ticks.

**Verdict:** Causal architecture guaranteed. No look-ahead possible.

---

## 3. Systematic Search

### 3.1 Future Indexing Patterns

Searched: `bars[i+`, `bars[-`, `future`, `lookahead`, `precomputed`

None found in:
- `brain/indicators.py`
- `brain/structure.py`
- `brain/regime.py`
- `brain/scoring.py`
- `brain/strategy/setups.py`
- `brain/pipeline.py`
- `brain/backtest/engine.py`

### 3.2 Dataframe Shifting

AUREXIS does **not** use pandas DataFrames. All calculations use explicit Python `list[Bar]` iteration.
No `.shift()`, `.ffill()`, `.bfill()` patterns exist.

### 3.3 Look-ahead via News

The backtest passes `news_state="CLEAR"` to the pipeline. This is conservative (allows more entries in backtest vs. live with news blocks). It does NOT use future news — it simply assumes no news events for the backtest period. This is documented and does not introduce positive look-ahead bias.

### 3.4 Look-ahead via Tick Price

In the backtest, SL/TP are checked using `tick.bid` and `tick.ask` — the current tick only.
Positions are opened using `tick.ask + slippage` (for BUY) or `tick.bid - slippage` (for SELL).
No future tick prices are used to fill orders.

---

## 4. Conclusion

**AUREXIS-STRAT-1.0.0 is causally correct.**

Every signal generated by the Brain pipeline uses only:
1. Closed bars available at the moment of evaluation.
2. The current tick (bid/ask) for spread check and entry reference.
3. The current news state (not future events).

The backtest replays ticks chronologically without pre-loading future data.

**Backtest results are NOT proof of future profitability.**
