/**
 * @jest-environment jsdom
 */
/** AUREXIS hook tests — risk and brain */

const mockRiskApi = { getState: jest.fn() };
const mockBrainApi = { getState: jest.fn() };

jest.mock("../lib/api", () => ({
  healthApi: { getHealth: jest.fn() },
  accountsApi: { list: jest.fn() },
  riskApi: mockRiskApi,
  brainApi: mockBrainApi,
  newsApi: { getState: jest.fn() },
  signalsApi: { list: jest.fn() },
  positionsApi: { list: jest.fn() },
  activityApi: { list: jest.fn() },
  agentsApi: { list: jest.fn() },
  marketApi: { getTick: jest.fn() },
  executionApi: { list: jest.fn() },
  performanceApi: { get: jest.fn() },
  backtestApi: { get: jest.fn() },
}));

let mockToken: string | null = null;
let mockIsAuthenticated = false;
jest.mock("../lib/auth-context", () => ({
  useAuth: () => ({ token: mockToken, isAuthenticated: mockIsAuthenticated, user: null, isLoading: false }),
}));

import { renderHook, waitFor } from "@testing-library/react";
import { useRisk } from "../lib/hooks/useRisk";
import { useBrain } from "../lib/hooks/useBrain";

beforeEach(() => { jest.clearAllMocks(); mockToken = null; mockIsAuthenticated = false; });

const RISK_NC = {
  account_id: "a1", risk_state: "NOT_CONFIGURED", trading_allowed: false,
  block_reason: "NOT_CONFIGURED", note: "UNDEFINED",
  parameters: { daily_loss_limit_usd: null, max_drawdown_usd: null, max_open_positions: null, risk_per_trade_pct: null, profit_lock_formula: "UNDEFINED", profit_lock_threshold_usd: "UNDEFINED", profit_lock_floor_pct: "UNDEFINED", drawdown_reference: "UNDEFINED", daily_reset_timezone: "UTC" },
};
const BRAIN_NC = {
  account_id: "a1", brain_state: "NOT_CONFIGURED", strategy_id: "AUREXIS-STRAT-1.0.0",
  strategy_version: "0.0.0", regime: "NOT_CONFIGURED", structure: "UNKNOWN",
  trend: "NOT_CONFIGURED", momentum: "NOT_CONFIGURED", volatility: "NOT_CONFIGURED",
  active_setup: "NOT_CONFIGURED", confidence: null, live_trading_enabled: false, note: "UNDEFINED",
};

describe("useRisk", () => {
  it("NO_ACCOUNT when accountId null", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    const { result } = renderHook(() => useRisk(null));
    await waitFor(() => expect(result.current.status).toBe("NO_ACCOUNT"));
    expect(mockRiskApi.getState).not.toHaveBeenCalled();
  });
  it("NO_ACCOUNT when token null", async () => {
    const { result } = renderHook(() => useRisk("acct-001"));
    await waitFor(() => expect(result.current.status).toBe("NO_ACCOUNT"));
    expect(mockRiskApi.getState).not.toHaveBeenCalled();
  });
  it("sends accountId and token", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockRiskApi.getState.mockResolvedValue(RISK_NC);
    renderHook(() => useRisk("acct-001"));
    await waitFor(() => expect(mockRiskApi.getState).toHaveBeenCalledWith("acct-001", "tok"));
  });
  it("preserves NOT_CONFIGURED — not coerced to NORMAL", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockRiskApi.getState.mockResolvedValue(RISK_NC);
    const { result } = renderHook(() => useRisk("acct-001"));
    await waitFor(() => expect(result.current.status).toBe("OK"));
    expect(result.current.data?.risk_state).toBe("NOT_CONFIGURED");
    expect(result.current.data?.risk_state).not.toBe("NORMAL");
    expect(result.current.data?.trading_allowed).toBe(false);
  });
  it("API error → ERROR state, null data", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockRiskApi.getState.mockRejectedValue(new Error("503"));
    const { result } = renderHook(() => useRisk("acct-001"));
    await waitFor(() => expect(result.current.status).toBe("ERROR"));
    expect(result.current.data).toBeNull();
  });
});

describe("useBrain", () => {
  it("NO_ACCOUNT when accountId null", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    const { result } = renderHook(() => useBrain(null));
    await waitFor(() => expect(result.current.status).toBe("NO_ACCOUNT"));
    expect(mockBrainApi.getState).not.toHaveBeenCalled();
  });
  it("NOT_CONFIGURED brain_state preserved", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockBrainApi.getState.mockResolvedValue(BRAIN_NC);
    const { result } = renderHook(() => useBrain("acct-001"));
    await waitFor(() => expect(result.current.status).toBe("OK"));
    expect(result.current.data?.brain_state).toBe("NOT_CONFIGURED");
    expect(result.current.data?.regime).toBe("NOT_CONFIGURED");
    expect(result.current.data?.live_trading_enabled).toBe(false);
  });
  it("error → null data, no fabricated brain", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockBrainApi.getState.mockRejectedValue(new Error("timeout"));
    const { result } = renderHook(() => useBrain("acct-001"));
    await waitFor(() => expect(result.current.status).toBe("ERROR"));
    expect(result.current.data).toBeNull();
  });
});
