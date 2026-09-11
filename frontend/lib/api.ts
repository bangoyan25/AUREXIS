/**
 * AUREXIS API client.
 *
 * Thin typed wrapper around fetch.
 * API base URL from NEXT_PUBLIC_API_URL env var — never hardcoded.
 * Tokens handled via Authorization header — NEVER in localStorage.
 */

import type { SystemHealth } from "@/types/domain";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(
  path: string,
  options?: RequestInit & { token?: string },
): Promise<T> {
  const { token, ...fetchOptions } = options ?? {};
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...fetchOptions.headers,
  };
  // 10-second hard timeout — prevents any fetch from hanging indefinitely
  // and leaving the app permanently in INITIALIZING state.
  // Caller-provided signal takes precedence; otherwise use AbortSignal.timeout.
  const signal: AbortSignal =
    (fetchOptions.signal as AbortSignal | null | undefined) ??
    AbortSignal.timeout(10_000);
  const res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, signal, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body, `API error ${res.status}: ${path}`);
  }
  return res.json() as Promise<T>;
}

// ── Domain types ──────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}
export interface MeResponse {
  user_id: string;
  email: string;
  display_name: string;
  is_superuser: boolean;
  created_at: string;
  tier?: number | null;
  account_limit?: number | null;
  license_status?: string | null;
  license_valid_until?: string | null;
}
export interface AccountResponse {
  id: string;
  label: string;
  broker: string;
  mt5_account_number: string;
  mt5_server: string | null;
  broker_currency: string;
  is_cent_account: boolean;
  cent_normalization_factor: string;
  is_active: boolean;
  trading_enabled: boolean;
  idr_conversion: string;
  created_at: string;
  updated_at: string;
}
export interface AgentResponse {
  id: string;
  account_id: string;
  label: string;
  last_known_status: string;
  last_seen_at: string | null;
  mt5_version: string | null;
  ea_version: string | null;
  notes: string | null;
  created_at: string;
}
export interface RegisterAgentResponse extends AgentResponse {
  // Returned exactly once at registration. Never exposed again.
  agent_secret: string;
}
export interface AuditEventResponse {
  id: string;
  event_type: string;
  severity: string;
  account_id: string | null;
  correlation_id: string | null;
  occurred_at: string;
}
export interface CommandResponse {
  id: string;
  agent_id: string;
  command_type: string;
  status: string;
  payload: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  sent_at: string | null;
  acknowledged_at: string | null;
  completed_at: string | null;
}

// ── Stub / domain response types ──────────────────────────────────────────────

export interface RiskStateResponse {
  account_id: string;
  risk_state: string;
  trading_allowed: boolean;
  block_reason: string;
  note: string;
  parameters: {
    daily_loss_limit_usd: number | null;
    max_drawdown_usd: number | null;
    max_open_positions: number | null;
    risk_per_trade_pct: number | null;
    profit_lock_formula: string;
    profit_lock_threshold_usd: string;
    profit_lock_floor_pct: string;
    drawdown_reference: string;
    daily_reset_timezone: string;
  };
}

export interface BrainStateResponse {
  account_id: string;
  brain_state: string;
  strategy_id: string;
  strategy_version: string;
  regime: string;
  structure: string;
  trend: string;
  momentum: string;
  volatility: string;
  active_setup: string;
  confidence: number | null;
  live_trading_enabled: boolean;
  note: string;
}

export interface MarketTickResponse {
  symbol: string;
  status: string;
  bid: number | null;
  ask: number | null;
  spread_pips: number | null;
  note: string;
}

export interface AccountMarketStateResponse {
  account_id: string;
  symbol: string;
  status: "FRESH" | "STALE" | "NO_DATA" | string;
  is_fresh: boolean;
  age_ms: number | null;
  bid: string | null;
  ask: string | null;
  spread: string | null;
  point: string | null;
  digits: number;
  tick_time: string | null;
  tick_volume: number;
  received_at: string | null;
}

export interface RiskDecisionResponse {
  decision: "ALLOW" | "BLOCK";
  reason_code: string;
  reason: string;
  symbol: string;
  timestamp: string;
  market_data: Record<string, unknown> | null;
  details: Record<string, unknown>;
  account_id: string;
}

export interface SignalsResponse {
  status: string;
  signals: unknown[];
  note: string;
}

export interface PositionsResponse {
  status: string;
  positions: unknown[];
  note: string;
}

export interface ExecutionResponse {
  status: string;
  commands: unknown[];
  note: string;
}

export interface NewsResponse {
  status: string;
  provider: string | null;
  upcoming_events: unknown[];
  pre_event_window_minutes: number;
  post_event_window_minutes: number;
  note: string;
}

export interface PerformanceResponse {
  status: string;
  total_trades: number;
  win_rate: number | null;
  total_pnl_usd: string;
  daily_pnl: Array<{ date: string; pnl_usd: string }>;
  note: string;
}

export interface BacktestResponse {
  status: string;
  note: string;
  results: unknown[];
}


// ── Health ────────────────────────────────────────────────────────────────────

export const healthApi = {
  getHealth: () => apiFetch<SystemHealth>("/api/v1/health"),
  getLiveness: () => apiFetch<{ status: string }>("/api/v1/health/live"),
  getReadiness: () => apiFetch<{ status: string }>("/api/v1/health/ready"),
};

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  register: (body: { email: string; password: string; display_name: string; serial_code: string }) =>
    apiFetch<MeResponse>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    apiFetch<TokenResponse>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(body) }),
  refresh: (refresh_token: string) =>
    apiFetch<TokenResponse>("/api/v1/auth/refresh", {
      method: "POST", body: JSON.stringify({ refresh_token }),
    }),
  logout: (token: string) =>
    apiFetch<void>("/api/v1/auth/logout", { method: "POST", token }),
  me: (token: string) =>
    apiFetch<MeResponse>("/api/v1/auth/me", { token }),
  forgotPassword: (body: { email: string }) =>
    apiFetch<{ message: string }>("/api/v1/auth/forgot-password", { method: "POST", body: JSON.stringify(body) }),
  resetPassword: (body: { token: string; new_password: string }) =>
    apiFetch<{ message: string }>("/api/v1/auth/reset-password", { method: "POST", body: JSON.stringify(body) }),
};

// ── Accounts ──────────────────────────────────────────────────────────────────

export const accountsApi = {
  list: (token: string) =>
    apiFetch<AccountResponse[]>("/api/v1/accounts", { token }),
  get: (id: string, token: string) =>
    apiFetch<AccountResponse>(`/api/v1/accounts/${id}`, { token }),
  create: (body: object, token: string) =>
    apiFetch<AccountResponse>("/api/v1/accounts", {
      method: "POST", body: JSON.stringify(body), token,
    }),
  patch: (id: string, body: object, token: string) =>
    apiFetch<AccountResponse>(`/api/v1/accounts/${id}`, {
      method: "PATCH", body: JSON.stringify(body), token,
    }),
  delete: (id: string, token: string) =>
    apiFetch<void>(`/api/v1/accounts/${id}`, { method: "DELETE", token }),
  getBrokers: (token: string) =>
    apiFetch<Array<{ id: string; name: string; servers: string[]; supports_cent: boolean }>>("/api/v1/accounts/brokers", { token }),
};

// ── Agents ────────────────────────────────────────────────────────────────────

export const agentsApi = {
  list: (token: string) =>
    apiFetch<AgentResponse[]>("/api/v1/agents", { token }),
  get: (id: string, token: string) =>
    apiFetch<AgentResponse>(`/api/v1/agents/${id}`, { token }),
  register: (body: { account_id: string; label: string; notes?: string | null }, token: string) =>
    apiFetch<RegisterAgentResponse>("/api/v1/agents", {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),
};

// ── Agent Commands ─────────────────────────────────────────────────────────────

export const commandsApi = {
  list: (agentId: string, token: string) =>
    apiFetch<CommandResponse[]>(`/api/v1/agents/${agentId}/commands`, { token }),
  get: (agentId: string, commandId: string, token: string) =>
    apiFetch<CommandResponse>(`/api/v1/agents/${agentId}/commands/${commandId}`, { token }),
  create: (agentId: string, body: { command_type: string; payload?: Record<string, unknown> }, token: string) =>
    apiFetch<CommandResponse>(`/api/v1/agents/${agentId}/commands`, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),
};

// ── Activity ──────────────────────────────────────────────────────────────────

export const activityApi = {
  list: (token: string, limit = 50) =>
    apiFetch<AuditEventResponse[]>(`/api/v1/activity?limit=${limit}`, { token }),
};

// ── Domain API (typed) ────────────────────────────────────────────────────────

export const riskApi = {
  getState: (accountId: string, token: string) =>
    apiFetch<RiskStateResponse>(`/api/v1/risk/${accountId}`, { token }),
  // Phase 3: authoritative server-side risk gate decision (ALLOW / BLOCK + reason_code)
  getDecision: (accountId: string, token: string) =>
    apiFetch<RiskDecisionResponse>(`/api/v1/risk/${accountId}/decision`, { token }),
};
export const brainApi = {
  getState: (accountId: string, token: string) =>
    apiFetch<BrainStateResponse>(`/api/v1/brain/${accountId}`, { token }),
};
export const marketApi = {
  getTick: (token: string) =>
    apiFetch<MarketTickResponse>("/api/v1/market/tick", { token }),
  // Phase 3: account-scoped live market tick & freshness
  getAccountState: (accountId: string, token: string) =>
    apiFetch<AccountMarketStateResponse>(`/api/v1/market/${accountId}/state`, { token }),
  getChart: (accountId: string, token: string, timeframe: string = "M5", limit: number = 100) =>
    apiFetch<{
      account_id: string;
      symbol: string;
      timeframe: string;
      count: number;
      bars: Array<{ time: string; open: number; high: number; low: number; close: number; volume: number }>;
      cached: boolean;
    }>(`/api/v1/market/${accountId}/chart?timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`, { token }),
};
export const signalsApi = {
  list: (token: string) =>
    apiFetch<SignalsResponse>("/api/v1/signals", { token }),
};
export const positionsApi = {
  list: (token: string) =>
    apiFetch<PositionsResponse>("/api/v1/positions", { token }),
};
export const executionApi = {
  list: (token: string) =>
    apiFetch<ExecutionResponse>("/api/v1/execution", { token }),
};
export const newsApi = {
  getState: (token: string) =>
    apiFetch<NewsResponse>("/api/v1/news", { token }),
};
export const performanceApi = {
  get: (token: string) =>
    apiFetch<PerformanceResponse>("/api/v1/performance", { token }),
};
export const backtestApi = {
  get: (token: string) =>
    apiFetch<BacktestResponse>("/api/v1/backtest", { token }),
};

// ── Strategy Engine ──────────────────────────────────────────────────────────

export interface StrategyStateResponse {
  account_id: string;
  enabled: boolean;
  dry_run: boolean;
  strategy_id: string;
  strategy_version: string;
  symbol: string;
  timeframe: string;
  last_signal_direction: string | null;
  last_signal_at: string | null;
  last_signal_candle_ts: string | null;
  last_signal_reason: string | null;
  last_risk_decision: string | null;
  last_risk_reason_code: string | null;
  last_execution_status: string | null;
  bars_count?: number;
  warmup_status?: string;
}

export interface StrategyBarsResponse {
  account_id: string;
  symbol: string;
  timeframe: string;
  count: number;
  first_candle_ts: string | null;
  last_candle_ts: string | null;
  bars: Array<{
    open_time: string;
    close_time: string;
    open: string;
    high: string;
    low: string;
    close: string;
    volume: string;
    is_closed: boolean;
  }>;
}

export interface StrategyEvaluateResponse {
  account_id: string;
  timestamp: string;
  signal_direction: string;
  signal_reason: string | null;
  risk_decision: string | null;
  risk_reason_code: string | null;
  execution_status: string;
  execution_reason: string | null;
  dry_run: boolean;
  candle_ts: string | null;
  signal_id: string | null;
  command_id?: string | null;
}

export interface LatestSignalResponse {
  account_id: string;
  signal: {
    id: string;
    symbol: string;
    direction: string;
    status: string;
    strategy_id: string;
    strategy_version: string;
    setup_type: string | null;
    confidence_score: string | null;
    entry_reference: string | null;
    suggested_stop_loss: string | null;
    suggested_take_profit: string | null;
    spread_at_signal: string | null;
    news_state_at_signal: string | null;
    generated_at: string;
    expires_at: string | null;
  } | null;
}

export const strategyApi = {
  getState: (accountId: string, token: string) =>
    apiFetch<StrategyStateResponse>(`/api/v1/accounts/${accountId}/strategy`, { token }),
  enable: (accountId: string, dry_run: boolean, token: string) =>
    apiFetch<StrategyStateResponse>(`/api/v1/accounts/${accountId}/strategy/enable`, {
      method: "POST",
      body: JSON.stringify({ dry_run }),
      token,
    }),
  disable: (accountId: string, token: string) =>
    apiFetch<StrategyStateResponse>(`/api/v1/accounts/${accountId}/strategy/disable`, {
      method: "POST",
      token,
    }),
  evaluate: (accountId: string, token: string) =>
    apiFetch<StrategyEvaluateResponse>(`/api/v1/accounts/${accountId}/strategy/evaluate`, {
      method: "POST",
      token,
    }),
  getLatestSignal: (accountId: string, token: string) =>
    apiFetch<LatestSignalResponse>(`/api/v1/accounts/${accountId}/strategy/signals/latest`, { token }),
  getKillSwitch: (accountId: string, token: string) =>
    apiFetch<{ account_id: string; kill_switch_active: boolean; status: string }>(
      `/api/v1/accounts/${accountId}/strategy/kill-switch`, { token }
    ),
  setKillSwitch: (accountId: string, active: boolean, token: string) =>
    apiFetch<{ account_id: string; kill_switch_active: boolean; status: string }>(
      `/api/v1/accounts/${accountId}/strategy/kill-switch`,
      { method: "POST", body: JSON.stringify({ active }), token }
    ),
  getBars: (accountId: string, token: string, timeframe: string = "M15") =>
    apiFetch<StrategyBarsResponse>(
      `/api/v1/accounts/${accountId}/strategy/bars?timeframe=${encodeURIComponent(timeframe)}`,
      { token }
    ),
};


export interface TestExecutionPayload {
  action: "OPEN_POSITION" | "CLOSE_POSITION";
  symbol?: string;
  side?: "BUY" | "SELL";
  volume?: string | number;
  position_ticket?: number | null;
  client_order_id: string;
  deviation?: number;
  comment?: string;
}

export interface TestExecutionResult {
  command_id: string;
  account_id: string;
  agent_id: string;
  client_order_id: string;
  action: string;
  symbol: string;
  side: string | null;
  volume: string;
  status: string;
  risk_decision: string;
  risk_reason_code: string;
  broker_result: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export const demoExecutionApi = {
  execute: (accountId: string, body: TestExecutionPayload, token: string) =>
    apiFetch<TestExecutionResult>(`/api/v1/accounts/${accountId}/execution/test`, {
      method: "POST",
      body: JSON.stringify(body),
      token,
    }),
  getStatus: (accountId: string, commandId: string, token: string) =>
    apiFetch<TestExecutionResult>(`/api/v1/accounts/${accountId}/execution/test/${commandId}`, { token }),
  getPositions: (accountId: string, token: string) =>
    apiFetch<{
      account_id: string;
      total_positions: number;
      open_positions: number;
      status: string;
      positions: Array<{
        id: string;
        broker_ticket: number;
        symbol: string;
        side: string;
        lots: string;
        open_price: string;
        close_price: string | null;
        status: string;
        opened_at: string | null;
        closed_at: string | null;
      }>;
    }>(`/api/v1/accounts/${accountId}/positions`, { token }),
};


