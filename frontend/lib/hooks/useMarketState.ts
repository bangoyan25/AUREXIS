"use client";
/**
 * useMarketState — GET /api/v1/market/{accountId}/state. Auth required. Account-scoped.
 * Returns AccountMarketStateResponse with live tick (bid, ask, spread, point, digits, tick_time, age_ms, status).
 * Polled every 2s while account is active.
 */
import { useState, useEffect, useCallback } from "react";
import { marketApi, type AccountMarketStateResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type MarketStateHookState =
  | { status: "NO_ACCOUNT"; data: null; error: null }
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: AccountMarketStateResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useMarketState(accountId: string | null) {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<MarketStateHookState>({
    status: "NO_ACCOUNT",
    data: null,
    error: null,
  });

  const fetchState = useCallback(async () => {
    if (!token || !isAuthenticated || !accountId) {
      setState({ status: "NO_ACCOUNT", data: null, error: null });
      return;
    }
    try {
      const data = await marketApi.getAccountState(accountId, token);
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load market state";
      setState((prev) => (prev.status === "OK" ? prev : { status: "ERROR", data: null, error: msg }));
    }
  }, [token, isAuthenticated, accountId]);

  useEffect(() => {
    if (!token || !isAuthenticated || !accountId) {
      setState({ status: "NO_ACCOUNT", data: null, error: null });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    void fetchState();

    const interval = setInterval(() => {
      void fetchState();
    }, 2000);

    return () => clearInterval(interval);
  }, [fetchState, token, isAuthenticated, accountId]);

  return { ...state, refetch: fetchState };
}
