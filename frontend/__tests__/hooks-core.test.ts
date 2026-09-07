/**
 * @jest-environment jsdom
 */
/** AUREXIS hook tests — health & accounts */

const mockHealthApi = { getHealth: jest.fn() };
const mockAccountsApi = { list: jest.fn() };

jest.mock("../lib/api", () => ({
  healthApi: mockHealthApi,
  accountsApi: mockAccountsApi,
  riskApi: { getState: jest.fn() },
  brainApi: { getState: jest.fn() },
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
import { useHealth } from "../lib/hooks/useHealth";
import { useAccounts } from "../lib/hooks/useAccounts";

beforeEach(() => { jest.clearAllMocks(); mockToken = null; mockIsAuthenticated = false; });

describe("useHealth", () => {
  it("starts LOADING", () => {
    mockHealthApi.getHealth.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useHealth());
    expect(result.current.status).toBe("LOADING");
    expect(result.current.data).toBeNull();
  });
  it("OK with backend data", async () => {
    mockHealthApi.getHealth.mockResolvedValue({
      status: "degraded", version: "0.1.0", environment: "test", check_duration_ms: 1,
      components: {
        backend: { status: "healthy" }, database: { status: "healthy" }, redis: { status: "healthy" },
        brain: { status: "NOT_CONFIGURED" }, risk_engine: { status: "NOT_CONFIGURED" },
        market_data: { status: "healthy" }, news: { status: "NOT_CONFIGURED" }, mt5: { status: "NO_AGENTS" },
      },
    });
    const { result } = renderHook(() => useHealth());
    await waitFor(() => expect(result.current.status).toBe("OK"));
    expect(result.current.data?.components.brain.status).toBe("NOT_CONFIGURED");
  });
  it("ERROR on API failure — null data, no mock fallback", async () => {
    mockHealthApi.getHealth.mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => useHealth());
    await waitFor(() => expect(result.current.status).toBe("ERROR"));
    expect(result.current.data).toBeNull();
  });
  it("NOT_CONFIGURED preserved — not coerced to healthy", async () => {
    mockHealthApi.getHealth.mockResolvedValue({
      status: "degraded", version: "0.1.0", environment: "test", check_duration_ms: 1,
      components: {
        backend: { status: "healthy" }, database: { status: "healthy" }, redis: { status: "healthy" },
        brain: { status: "NOT_CONFIGURED" }, risk_engine: { status: "NOT_CONFIGURED" },
        market_data: { status: "healthy" }, news: { status: "NOT_CONFIGURED" }, mt5: { status: "NO_AGENTS" },
      },
    });
    const { result } = renderHook(() => useHealth());
    await waitFor(() => expect(result.current.status).toBe("OK"));
    expect(result.current.data?.components.brain.status).not.toBe("healthy");
  });
});

describe("useAccounts", () => {
  it("no request when unauthenticated", async () => {
    const { result } = renderHook(() => useAccounts());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(mockAccountsApi.list).not.toHaveBeenCalled();
    expect(result.current.accounts).toHaveLength(0);
  });
  it("sends token in request", async () => {
    mockToken = "tok-123"; mockIsAuthenticated = true;
    mockAccountsApi.list.mockResolvedValue([]);
    renderHook(() => useAccounts());
    await waitFor(() => expect(mockAccountsApi.list).toHaveBeenCalledWith("tok-123"));
  });
  it("error → empty accounts, no fabrication", async () => {
    mockToken = "tok-123"; mockIsAuthenticated = true;
    mockAccountsApi.list.mockRejectedValue(new Error("403"));
    const { result } = renderHook(() => useAccounts());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.accounts).toHaveLength(0);
    expect(result.current.error).toBeTruthy();
  });
});
