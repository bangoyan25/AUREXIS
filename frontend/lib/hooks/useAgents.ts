"use client";
/**
 * useAgents — GET /api/v1/agents + register. Auth required.
 */
import { useState, useEffect, useCallback } from "react";
import { agentsApi, type AgentResponse, type RegisterAgentResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export function useAgents() {
  const { token, isAuthenticated } = useAuth();
  const [data, setData] = useState<AgentResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setData([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await agentsApi.list(token);
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load agents";
      setError(msg);
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [token, isAuthenticated]);

  useEffect(() => { void fetchAgents(); }, [fetchAgents]);

  const registerAgent = useCallback(
    async (body: { account_id: string; label: string; notes?: string | null }): Promise<RegisterAgentResponse> => {
      if (!token) throw new Error("Unauthenticated");
      const result = await agentsApi.register(body, token);
      await fetchAgents();
      return result;
    },
    [token, fetchAgents],
  );

  return { data, agents: data, loading, error, refetch: fetchAgents, registerAgent };
}

