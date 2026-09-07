/**
 * @jest-environment jsdom
 */
/** AUREXIS hook tests — news, positions, state semantics */

const mockRiskApi = { getState: jest.fn() };
const mockNewsApi = { getState: jest.fn() };
const mockPositionsApi = { list: jest.fn() };

jest.mock("../lib/api", () => ({
  healthApi: { getHealth: jest.fn() },
  accountsApi: { list: jest.fn() },
  riskApi: mockRiskApi,
  brainApi: { getState: jest.fn() },
  newsApi: mockNewsApi,
  signalsApi: { list: jest.fn() },
  positionsApi: mockPositionsApi,
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
import { useNews } from "../lib/hooks/useNews";
import { usePositions } from "../lib/hooks/usePositions";
import { useRisk } from "../lib/hooks/useRisk";

beforeEach(() => { jest.clearAllMocks(); mockToken = null; mockIsAuthenticated = false; });

const RISK_NC = {
  account_id: "a1", risk_state: "NOT_CONFIGURED", trading_allowed: false,
  block_reason: "NOT_CONFIGURED", note: "UNDEFINED",
  parameters: { daily_loss_limit_usd: null, max_drawdown_usd: null, max_open_positions: null, risk_per_trade_pct: null, profit_lock_formula: "UNDEFINED", profit_lock_threshold_usd: "UNDEFINED", profit_lock_floor_pct: "UNDEFINED", drawdown_reference: "UNDEFINED", daily_reset_timezone: "UTC" },
};

describe("useNews", () => {
  it("UNKNOWN state preserved — not coerced to CLEAR", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockNewsApi.getState.mockResolvedValue({ status: "UNKNOWN", provider: null, upcoming_events: [], pre_event_window_minutes: 60, post_event_window_minutes: 30, note: "fail-closed" });
    const { result } = renderHook(() => useNews());
    await waitFor(() => expect(result.current.status).toBe("OK"));
    expect(result.current.data?.status).toBe("UNKNOWN");
    expect(result.current.data?.status).not.toBe("CLEAR");
  });
  it("unauthenticated → ERROR, no news API call", async () => {
    const { result } = renderHook(() => useNews());
    await waitFor(() => expect(result.current.status).toBe("ERROR"));
    expect(result.current.data).toBeNull();
    expect(mockNewsApi.getState).not.toHaveBeenCalled();
  });
});

describe("usePositions", () => {
  it("EMPTY positions — EMPTY ≠ fabricated", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockPositionsApi.list.mockResolvedValue({ status: "EMPTY", positions: [], note: "No positions" });
    const { result } = renderHook(() => usePositions());
    await waitFor(() => expect(result.current.status).toBe("OK"));
    expect(result.current.data?.positions).toHaveLength(0);
    expect(result.current.data?.status).toBe("EMPTY");
  });
  it("API error → ERROR, null data — no mock positions", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockPositionsApi.list.mockRejectedValue(new Error("gateway error"));
    const { result } = renderHook(() => usePositions());
    await waitFor(() => expect(result.current.status).toBe("ERROR"));
    expect(result.current.data).toBeNull();
  });
});

describe("State semantics — invariants", () => {
  it("NOT_CONFIGURED ≠ NORMAL", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockRiskApi.getState.mockResolvedValue(RISK_NC);
    const { result } = renderHook(() => useRisk("a1"));
    await waitFor(() => expect(result.current.status).toBe("OK"));
    expect(result.current.data?.risk_state).not.toBe("NORMAL");
  });
  it("BLOCKED ≠ AUTHORIZED — trading_allowed false when NOT_CONFIGURED", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockRiskApi.getState.mockResolvedValue(RISK_NC);
    const { result } = renderHook(() => useRisk("a1"));
    await waitFor(() => expect(result.current.status).toBe("OK"));
    expect(result.current.data?.trading_allowed).toBe(false);
  });
  it("UNKNOWN news ≠ CLEAR", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockNewsApi.getState.mockResolvedValue({ status: "UNKNOWN", provider: null, upcoming_events: [], pre_event_window_minutes: 60, post_event_window_minutes: 30, note: "fail-closed" });
    const { result } = renderHook(() => useNews());
    await waitFor(() => expect(result.current.status).toBe("OK"));
    expect(result.current.data?.status).not.toBe("CLEAR");
  });
  it("API error → ERROR not mock success", async () => {
    mockToken = "tok"; mockIsAuthenticated = true;
    mockRiskApi.getState.mockRejectedValue(new Error("503"));
    const { result } = renderHook(() => useRisk("a1"));
    await waitFor(() => expect(result.current.status).toBe("ERROR"));
    expect(result.current.data).toBeNull();
  });
});
