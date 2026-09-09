"use client";
/**
 * useAgentCommands — GET /api/v1/agents/{agentId}/commands. Auth required.
 */
import { useState, useEffect, useCallback } from "react";
import { commandsApi, type CommandResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export function useAgentCommands(agentId: string | null) {
  const { token, isAuthenticated } = useAuth();
  const [data, setData] = useState<CommandResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState<boolean>(false);

  const fetchCommands = useCallback(async () => {
    if (!token || !isAuthenticated || !agentId) {
      setData([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await commandsApi.list(agentId, token);
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load commands";
      setError(msg);
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [token, isAuthenticated, agentId]);

  useEffect(() => { void fetchCommands(); }, [fetchCommands]);

  const sendCommand = useCallback(async (commandType: "PING" | "GET_STATUS") => {
    if (!token || !agentId) throw new Error("Unauthenticated");
    setSending(true);
    try {
      const cmd = await commandsApi.create(agentId, { command_type: commandType }, token);
      await fetchCommands();
      return cmd;
    } finally {
      setSending(false);
    }
  }, [token, agentId, fetchCommands]);

  return { data, commands: data, loading, error, refetch: fetchCommands, sendCommand, sending };
}
