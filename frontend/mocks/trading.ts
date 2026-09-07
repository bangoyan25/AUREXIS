/** MOCK — risk, brain, news data */
import type { RiskSnapshot, BrainSnapshot, NewsSnapshot, MarketTick } from "@/types/domain";

export const MOCK_RISK: RiskSnapshot = {
  account_id: "mock-account-001",
  state: "NOT_CONFIGURED",
  current_equity_usd: 0, balance_usd: 0, equity_peak_usd: 0,
  current_drawdown_usd: 0, current_drawdown_pct: 0,
  daily_realized_pnl_usd: 0, daily_loss_limit_usd: null, daily_loss_utilization_pct: null,
  open_exposure_usd: 0, position_count: 0,
  trading_allowed: false, block_reason: "Risk Engine not configured", block_code: "NOT_CONFIGURED",
  profit_lock: { active: false, stage: null, session_peak_usd: null, protected_usd: null, current_pnl_usd: null, lock_threshold_usd: null, next_lock_distance: null },
  snapshot_at: "2026-09-06T00:00:00Z",
};

export const MOCK_BRAIN: BrainSnapshot = {
  account_id: "mock-account-001",
  market_state: "INITIALIZING",
  regime: "NOT_CONFIGURED",
  strategy_version: "0.0.0-not-configured",
  structure: {
    htf_structure: "UNKNOWN", mtf_structure: "UNKNOWN",
    trend_direction: "NEUTRAL", trend_strength: "FLAT",
    regime: "NOT_CONFIGURED", momentum_state: "NEUTRAL", volatility_state: "NORMAL",
    structure_aligned: false, trend_aligned: false, updated_at: "2026-09-06T00:00:00Z",
  },
  pipeline: [
    { name: "Market Data",      state: "INITIALIZING",     status: "UNKNOWN",        updated_at: "2026-09-06T00:00:00Z" },
    { name: "Regime",           state: "NOT_CONFIGURED",   status: "NOT_CONFIGURED", detail: "HTF/MTF timeframes UNDEFINED", updated_at: "2026-09-06T00:00:00Z" },
    { name: "Structure",        state: "INSUFFICIENT_DATA",status: "NOT_CONFIGURED", updated_at: "2026-09-06T00:00:00Z" },
    { name: "Trend",            state: "NOT_CONFIGURED",   status: "NOT_CONFIGURED", detail: "EMA period UNDEFINED",  updated_at: "2026-09-06T00:00:00Z" },
    { name: "Setup",            state: "NOT_CONFIGURED",   status: "NOT_CONFIGURED", updated_at: "2026-09-06T00:00:00Z" },
    { name: "Breakout/Fakeout", state: "NOT_CONFIGURED",   status: "NOT_CONFIGURED", updated_at: "2026-09-06T00:00:00Z" },
    { name: "Momentum",         state: "NOT_CONFIGURED",   status: "NOT_CONFIGURED", detail: "RSI period UNDEFINED",  updated_at: "2026-09-06T00:00:00Z" },
    { name: "Volatility",       state: "NOT_CONFIGURED",   status: "NOT_CONFIGURED", detail: "ATR period UNDEFINED",  updated_at: "2026-09-06T00:00:00Z" },
    { name: "Confidence",       state: "NOT_CONFIGURED",   status: "NOT_CONFIGURED", detail: "Scoring formula UNDEFINED", updated_at: "2026-09-06T00:00:00Z" },
    { name: "News",             state: "UNKNOWN",           status: "NOT_CONFIGURED", detail: "Provider UNDEFINED",   updated_at: "2026-09-06T00:00:00Z" },
    { name: "Risk Gate",        state: "BLOCKED",           status: "BLOCKED",        detail: "Risk Engine NOT_CONFIGURED", updated_at: "2026-09-06T00:00:00Z" },
    { name: "Execution",        state: "BLOCKED",           status: "BLOCKED",        detail: "No MT5 agents",        updated_at: "2026-09-06T00:00:00Z" },
  ],
  no_trade_reason: "Strategy parameters not configured. All production parameters are UNDEFINED pending backtest calibration.",
  no_trade_code: "INDICATOR_NOT_CONFIGURED",
  updated_at: "2026-09-06T00:00:00Z",
};

export const MOCK_NEWS: NewsSnapshot = {
  state: "UNKNOWN",
  checked_at: "2026-09-06T00:00:00Z",
};

export const MOCK_TICK: MarketTick = {
  symbol: "XAUUSD", bid: 0, ask: 0, spread_pts: 0,
  timestamp: "2026-09-06T00:00:00Z", received_at: "2026-09-06T00:00:00Z",
};
