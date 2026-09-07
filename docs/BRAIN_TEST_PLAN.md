# AUREXIS Brain Test Plan

> Pre-implementation test specification. Tests conceptual; no code written yet.
> Existing 138/138 pass, unaffected. Tests written after specification approval.

---

## 1. Market Structure

| Test | Input | Expected |
|------|-------|---------|
| `test_swing_high_confirmed` | H[i] > N bars before and after | `True` |
| `test_swing_high_not_yet_confirmed` | N future bars not closed | `False` |
| `test_swing_high_fails_future_bar` | One future bar higher | `False` |
| `test_swing_low_confirmed` | L[i] < N bars before and after | `True` |
| `test_swing_tie_conservative` | H[i]==H[i+1] | `False` |
| `test_hh` | SH₁ > SH₀ | HH |
| `test_hl` | SL₁ > SL₀ | HL |
| `test_lh` | SH₁ < SH₀ | LH |
| `test_ll` | SL₁ < SL₀ | LL |
| `test_ambiguous` | No consistent progression | RANGING |
| `test_insufficient_data` | Below min swing count | INSUFFICIENT_DATA |
| `test_bos_up` | Close > SH₁ + MIN_BOS_DISTANCE | BOS_UP |
| `test_bos_down` | Close < SL₁ - MIN_BOS_DISTANCE | BOS_DOWN |
| `test_bos_wick_rejected` | Wick above SH₁, close below | No BOS |
| `test_bos_micro_rejected` | Close > SH₁ by < MIN_BOS_DISTANCE | No BOS |
| `test_choch` | BOS_DOWN in BULLISH | CHoCH, TRANSITION |

---

## 2. Regime

| Test | Expected |
|------|---------|
| `test_trend_up` | TREND_UP |
| `test_trend_down` | TREND_DOWN |
| `test_range` | RANGE |
| `test_transition_on_choch` | TRANSITION |
| `test_high_volatility` | HIGH_VOLATILITY |
| `test_unknown_insufficient_data` | UNKNOWN |
| `test_unknown_contradiction` | UNKNOWN |
| `test_anti_flapping_reverts` | Revert to previous regime |
| `test_anti_flapping_commits` | Commit new regime after N bars |
| `test_unknown_no_signal` | direction=NONE |
| `test_high_vol_no_signal` | direction=NONE |

---

## 3. Breakout

| Test | Expected |
|------|---------|
| `test_valid_breakout` | Breakout valid |
| `test_weak_distance` | Not a breakout |
| `test_spread_too_wide` | Blocked, spread_too_wide event |
| `test_volatility_abnormal` | Blocked |
| `test_news_blocked` | NEWS_BLOCKED |
| `test_momentum_neutral` | Reduced confidence |
| `test_regime_incompatible` | REGIME_INCOMPATIBLE |

---

## 4. Fakeout

| Test | Expected |
|------|---------|
| `test_valid_fakeout` | BULLISH_FAKEOUT or BEARISH_FAKEOUT |
| `test_wick_only_rejected` | Not a fakeout |
| `test_return_wick_only` | Not yet fakeout |
| `test_second_close_beyond` | Setup invalidated |
| `test_ambiguous_oscillation` | CANDIDATE_FORMING |

---

## 5. Signal Lifecycle

| Test | Expected |
|------|---------|
| `test_full_alignment` | Signal forwarded |
| `test_partial_low_confidence` | Confidence reduced |
| `test_htf_mtf_conflict` | HTF_MTF_MISALIGNMENT |
| `test_signal_expiry` | EXPIRED |
| `test_duplicate_blocked` | DUPLICATE_SIGNAL_ACTIVE |
| `test_signal_invalidated` | INVALIDATED |
| `test_news_blocked_then_clears` | NEWS_BLOCKED → CANDIDATE_READY |
| `test_news_unknown_conservative` | Treated as PRE_EVENT |

---

## 6. Safety (Every Must Result in NO TRADE)

| Test | Condition |
|------|-----------|
| `test_market_warming_up` | State = WARMING_UP |
| `test_stale_data` | No tick within threshold |
| `test_news_unknown` | News UNKNOWN |
| `test_risk_engine_error` | Risk Engine exception |
| `test_account_emergency` | Risk Engine EMERGENCY |
| `test_not_configured` | Required param None |
| `test_indicator_cold` | Below min bar count |
| `test_spread_too_wide` | Spread > max |
| `test_emergency_overrides_all` | emergency_stop_active=True |

---

## 7. Anti-Look-Ahead (Backtest)

| Test | Scenario | Expected |
|------|---------|---------|
| `test_no_bar_indicator_on_open_bar` | Tick on unclosed bar | Indicator unchanged |
| `test_no_structure_on_open_bar` | Tick on unclosed bar | Structure unchanged |
| `test_swing_unconfirmed` | N future bars not closed | Not confirmed |
| `test_bos_waits_for_close` | Bar high exceeds SH₁ intrabar | BOS waits |
| `test_replay_no_future_data` | Replay at T | T+1 inaccessible |

---

## 8. Current Test Status

```
.venv\Scripts\pytest.exe tests/ -q
```

138/138 passing. No new tests added in this phase.
New Brain tests to be written after specification approval.
