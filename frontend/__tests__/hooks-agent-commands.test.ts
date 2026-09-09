/**
 * @jest-environment jsdom
 */
import { renderHook, waitFor, act } from "@testing-library/react";

const mockAgentsApi = {
  list: jest.fn(),
  get: jest.fn(),
};

const mockCommandsApi = {
  list: jest.fn(),
  get: jest.fn(),
  create: jest.fn(),
};

jest.mock("../lib/api", () => ({
  agentsApi: mockAgentsApi,
  commandsApi: mockCommandsApi,
  healthApi: { getHealth: jest.fn() },
  accountsApi: { list: jest.fn() },
  riskApi: { getState: jest.fn() },
  brainApi: { getState: jest.fn() },
  newsApi: { getState: jest.fn() },
  signalsApi: { list: jest.fn() },
  positionsApi: { list: jest.fn() },
  activityApi: { list: jest.fn() },
  marketApi: { getTick: jest.fn() },
  executionApi: { list: jest.fn() },
  performanceApi: { get: jest.fn() },
  backtestApi: { get: jest.fn() },
}));

let mockToken: string | null = null;
let mockIsAuthenticated = false;

jest.mock("../lib/auth-context", () => ({
  useAuth: () => ({
    token: mockToken,
    isAuthenticated: mockIsAuthenticated,
    user: mockIsAuthenticated ? { user_id: "u-1", email: "trader@aurexis.local" } : null,
    isLoading: false,
  }),
}));

import { useAgents } from "../lib/hooks/useAgents";
import { useAgentCommands } from "../lib/hooks/useAgentCommands";

beforeEach(() => {
  jest.clearAllMocks();
  mockToken = null;
  mockIsAuthenticated = false;
});

describe("useAgents", () => {
  it("returns empty when unauthenticated", async () => {
    const { result } = renderHook(() => useAgents());
    expect(result.current.loading).toBe(false);
    expect(result.current.agents).toEqual([]);
    expect(mockAgentsApi.list).not.toHaveBeenCalled();
  });

  it("fetches agent list when authenticated", async () => {
    mockToken = "valid-jwt";
    mockIsAuthenticated = true;
    mockAgentsApi.list.mockResolvedValue([
      {
        id: "ag-123",
        account_id: "acc-1",
        label: "MT5 Agent EURUSD",
        last_known_status: "CONNECTED",
        last_seen_at: "2026-09-09T12:00:00Z",
        ea_version: "0.1.0",
        mt5_version: "5.0",
        notes: null,
        created_at: "2026-09-09T00:00:00Z",
      },
    ]);

    const { result } = renderHook(() => useAgents());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.agents).toHaveLength(1);
    expect(result.current.agents[0].id).toBe("ag-123");
    expect(result.current.agents[0].last_known_status).toBe("CONNECTED");
  });

  it("sets error state on failure", async () => {
    mockToken = "valid-jwt";
    mockIsAuthenticated = true;
    mockAgentsApi.list.mockRejectedValue(new Error("Network failed"));

    const { result } = renderHook(() => useAgents());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Network failed");
    expect(result.current.agents).toEqual([]);
  });
});

describe("useAgentCommands", () => {
  const agentId = "3c511fdb-0759-4c60-aef9-08215a5f57a6";

  it("does not fetch commands when agentId is null", async () => {
    mockToken = "valid-jwt";
    mockIsAuthenticated = true;

    const { result } = renderHook(() => useAgentCommands(null));
    expect(result.current.loading).toBe(false);
    expect(result.current.commands).toEqual([]);
    expect(mockCommandsApi.list).not.toHaveBeenCalled();
  });

  it("loads command history on mount", async () => {
    mockToken = "valid-jwt";
    mockIsAuthenticated = true;
    mockCommandsApi.list.mockResolvedValue([
      {
        id: "cmd-1",
        agent_id: agentId,
        command_type: "PING",
        status: "COMPLETED",
        payload: null,
        result: { pong: true },
        error_message: null,
        created_at: "2026-09-09T10:00:00Z",
        completed_at: "2026-09-09T10:00:01Z",
      },
    ]);

    const { result } = renderHook(() => useAgentCommands(agentId));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.commands).toHaveLength(1);
    expect(result.current.commands[0].command_type).toBe("PING");
    expect(result.current.commands[0].status).toBe("COMPLETED");
  });

  it("dispatches PING command and refetches", async () => {
    mockToken = "valid-jwt";
    mockIsAuthenticated = true;
    mockCommandsApi.list.mockResolvedValue([]);
    mockCommandsApi.create.mockResolvedValue({
      id: "cmd-2",
      agent_id: agentId,
      command_type: "PING",
      status: "PENDING",
      payload: null,
      result: null,
      error_message: null,
      created_at: "2026-09-09T10:05:00Z",
    });

    const { result } = renderHook(() => useAgentCommands(agentId));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.sendCommand("PING");
    });

    expect(mockCommandsApi.create).toHaveBeenCalledWith(
      agentId,
      { command_type: "PING" },
      "valid-jwt",
    );
    expect(mockCommandsApi.list).toHaveBeenCalledTimes(2);
  });
});
