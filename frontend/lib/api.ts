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
  const res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers });
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
export interface AuditEventResponse {
  id: string;
  event_type: string;
  severity: string;
  account_id: string | null;
  correlation_id: string | null;
  occurred_at: string;
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
  daily_pnl: unknown[];
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
  register: (body: { email: string; password: string; display_name: string }) =>
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
};

// ── Agents ────────────────────────────────────────────────────────────────────

export const agentsApi = {
  list: (token: string) =>
    apiFetch<AgentResponse[]>("/api/v1/agents", { token }),
  get: (id: string, token: string) =>
    apiFetch<AgentResponse>(`/api/v1/agents/${id}`, { token }),
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
};
export const brainApi = {
  getState: (accountId: string, token: string) =>
    apiFetch<BrainStateResponse>(`/api/v1/brain/${accountId}`, { token }),
};
export const marketApi = {
  getTick: (token: string) =>
    apiFetch<MarketTickResponse>("/api/v1/market/tick", { token }),
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

