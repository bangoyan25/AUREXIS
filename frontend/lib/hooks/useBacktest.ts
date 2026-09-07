"use client";
/**
 * useBacktest — GET /api/v1/backtest. Auth required.
 * Preserves backend state (e.g. status: NOT_CONFIGURED, results: []).
 */
import { useState, useEffect, useCallback } from "react";
import { backtestApi, type BacktestResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type BacktestHookState =
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: BacktestResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useBacktest() {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<BacktestHookState>({ status: "LOADING", data: null, error: null });

  const fetchBacktest = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setState({ status: "ERROR", data: null, error: "Not authenticated" });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    try {
      const data = await backtestApi.get(token);
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load backtest";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, [token, isAuthenticated]);

  useEffect(() => { void fetchBacktest(); }, [fetchBacktest]);

  return { ...state, refetch: fetchBacktest };
}
