# AUREXIS Strategy Parameters — AUREXIS-STRAT-1.0.0

**Status:** INITIAL DEFAULTS LOCKED — 2026-09-06
**Strategy ID:** `AUREXIS_CORE`
**Strategy Version:** `AUREXIS-STRAT-1.0.0`
**Live Trading Status:** DISABLED

---

## 1. Overview

Structure-First, Regime-Aware, Breakout/Fakeout, Trend-Confirmation system.
6 independent evidence dimensions: Structure(25%), Setup(25%), Trend(20%), Momentum(10%), Volatility(10%), Regime(10%).
Min confidence threshold: 0.70. All parameters in `brain/config.py`.

---

## 2. Timeframe Hierarchy

| Layer | TF | Role |
|-------|----|------|
| HTF | M15 | Macro structure + trend |
| MTF | M5 | Setup formation, indicators |
| Execution | Tick | Live price, spread, staleness |

---

## 3. Parameters

### 3.1 Structure (`StructureConfig`)

| Param | Default | Rationale |
|-------|---------|-----------|
| `swing_lookback_bars` | 3 | 3 bars left + 3 right — conservative for 5m XAUUSD |
| `min_bos_atr_multiplier` | 0.30 | BOS must displace >= 0.30 × ATR |
| `equal_level_tolerance_atr` | 0.10 | Within 0.10 × ATR = equal level |
| `max_level_age_bars` | 100 | Levels expire after 100 MTF bars |

### 3.2 Regime (`RegimeConfig`)

| Param | Default | Rationale |
|-------|---------|-----------|
| `adx_period` | 14 | Wilder standard period |
| `trending_threshold` | 20.0 | ADX >= 20 = TRENDING |
| `regime_confirmation_bars` | 2 | Anti-flapping hysteresis |
| `volatility_baseline_bars` | 50 | Rolling normalization window |
| `volatility_normal_ratio` | 1.50 | ATR/baseline <= 1.50 = NORMAL |
| `volatility_high_ratio` | 2.00 | ATR/baseline >= 2.00 = ABNORMAL_HIGH → HARD BLOCK |

### 3.3 Trend (`TrendConfig`)

| Param | Default | Rationale |
|-------|---------|-----------|
| `fast_ma_period` | 20 | 20 EMA on MTF |
| `slow_ma_period` | 50 | 50 EMA on MTF |
| `trend_consistency_bars` | 3 | Fast must stay above/below slow for 3 bars |

### 3.4 Momentum (`MomentumConfig`)

| Param | Default | Rationale |
|-------|---------|-----------|
| `rsi_period` | 14 | Wilder standard period |
| `rsi_bullish_min` | 52.0 | RSI > 52 = bullish |
| `rsi_bearish_max` | 48.0 | RSI < 48 = bearish |
| `rsi_overbought` | 70.0 | EXHAUSTED in uptrend |
| `rsi_oversold` | 30.0 | EXHAUSTED in downtrend |

### 3.5 Volatility (`VolatilityConfig`)

| Param | Default | Rationale |
|-------|---------|-----------|
| `atr_period` | 14 | ATR for SL + distance |
| `atr_baseline_bars` | 50 | Normalization window |
| `normal_ratio_upper` | 1.50 | NORMAL upper bound |
| `abnormal_high_ratio` | 2.00 | ABNORMAL_HIGH hard block |
| `max_atr_threshold_usd` | 15.00 | Absolute XAUUSD safety ceiling |

### 3.6 Breakout/Fakeout (`BreakoutConfig`)

| Param | Default | Rationale |
|-------|---------|-----------|
| `breakout_confirmation_bars` | 1 | Closed bar beyond level |
| `min_displacement_atr` | 0.30 | Min displacement for valid breakout |
| `setup_expiry_bars` | 3 | 3 MTF bars (~15 min) — expired = NO TRADE |
| `fakeout_reversal_bars` | 1 | 1 bar back inside structure |

### 3.7 Scoring (`ScoringConfig`)

| Dimension | Weight | Description |
|-----------|--------|-------------|
| structure | 25% | Swing bias, BOS/CHoCH |
| setup | 25% | Breakout/fakeout quality |
| trend | 20% | EMA order + ADX |
| momentum | 10% | RSI state |
| volatility | 10% | ATR normalized state |
| regime | 10% | Macro regime fit |
| **min_confidence_threshold** | — | **0.70** |

### 3.8 SL/TP (`SlTpConfig`)

| Param | Default | Rationale |
|-------|---------|-----------|
| `sl_atr_buffer` | 0.50 | Buffer beyond structural invalidation |
| `min_sl_atr` | 0.30 | Min SL distance (< = reject) |
| `rr_target` | 2.0 | TP = entry ± (risk × 2.0) |
| `min_rr` | 1.5 | Min R:R (below = reject) |

### 3.9 Protection (`SpreadConfig`, `FreshnessConfig`)

| Param | Default | Rationale |
|-------|---------|-----------|
| `max_spread_usd` | 1.00 | Max spread in USD for entry |
| `max_tick_staleness_ms` | 2000 | STALE threshold in ms |

---

## 4. Hard Gates (override confidence)

1. Market data != READY
2. Tick staleness > 2000ms
3. Spread > $1.00
4. News != CLEAR
5. Regime in UNKNOWN, HIGH_VOLATILITY, TRANSITION
6. Brain not configured

---

## 5. Disclaimer

**Backtest results are not proof of future profitability.**
Live trading remains DISABLED.
