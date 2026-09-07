"use client";
/**
 * usePerformance — GET /api/v1/performance. Auth required.
 * Preserves backend state (e.g. status: EMPTY, total_trades: 0).
 */
import { useState, useEffect, useCallback } from "react";
import { performanceApi, type PerformanceResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type PerformanceHookState =
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: PerformanceResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function usePerformance() {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<PerformanceHookState>({ status: "LOADING", data: null, error: null });

  const fetchPerformance = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setState({ status: "ERROR", data: null, error: "Not authenticated" });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    try {
      const data = await performanceApi.get(token);
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load performance metrics";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, [token, isAuthenticated]);

  useEffect(() => { void fetchPerformance(); }, [fetchPerformance]);

  return { ...state, refetch: fetchPerformance };
}
