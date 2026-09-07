/** MOCK — positions, signals, commands, trades, PNL, performance, backtest */
import type {
  LivePosition, CandidateSignal, ExecutionCommand,
  ClosedTrade, DailyPnl, PerformanceStats, BacktestResult,
} from "@/types/domain";

export const MOCK_POSITIONS:  LivePosition[]    = [];
export const MOCK_SIGNALS:    CandidateSignal[] = [];
export const MOCK_COMMANDS:   ExecutionCommand[] = [];
export const MOCK_TRADES:     ClosedTrade[]     = [];
export const MOCK_PNL:        DailyPnl[]        = [];

export const MOCK_PERFORMANCE: PerformanceStats = {
  account_id: "mock-account-001",
  period_start: "2026-09-01", period_end: "2026-09-06",
  total_trades: 0, winning_trades: 0, losing_trades: 0,
  win_rate_pct: 0, total_pnl_usd: 0, avg_win_usd: 0, avg_loss_usd: 0,
  max_drawdown_usd: 0, max_drawdown_pct: 0,
  profit_factor: null, sharpe_ratio: null, avg_duration_seconds: 0,
};

export const MOCK_BACKTEST: BacktestResult = {
  run_id: "mock-run-001",
  status: "NOT_CONFIGURED",
  started_at: "2026-09-06T00:00:00Z",
  config: {
    dataset_id: "", symbol: "XAUUSD",
    date_range_start: "", date_range_end: "",
    timeframe_htf: null, timeframe_mtf: null,
    strategy_version: "0.0.0-not-configured",
    config_version: "UNDEFINED",
    execution_model: "MARKET",
    spread_model: "FIXED", spread_pts: null,
    slippage_model: "ZERO", slippage_pts: null,
    commission_usd: null, swap_enabled: false, news_replay: false, risk_engine: false,
  },
};
