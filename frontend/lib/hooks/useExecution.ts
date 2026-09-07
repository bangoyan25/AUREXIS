"use client";
/**
 * useExecution — GET /api/v1/execution. Auth required.
 * Preserves backend state (e.g. status: EMPTY, commands: []).
 */
import { useState, useEffect, useCallback } from "react";
import { executionApi, type ExecutionResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type ExecutionHookState =
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: ExecutionResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useExecution() {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<ExecutionHookState>({ status: "LOADING", data: null, error: null });

  const fetchExecution = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setState({ status: "ERROR", data: null, error: "Not authenticated" });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    try {
      const data = await executionApi.list(token);
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load execution history";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, [token, isAuthenticated]);

  useEffect(() => { void fetchExecution(); }, [fetchExecution]);

  return { ...state, refetch: fetchExecution };
}
