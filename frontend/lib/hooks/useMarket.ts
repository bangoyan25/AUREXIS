"use client";
/**
 * useMarket — GET /api/v1/market/tick. Auth required.
 * Returns MarketTickResponse — backend status preserved (NOT_CONFIGURED, UNKNOWN, etc.)
 */
import { useState, useEffect, useCallback } from "react";
import { marketApi, type MarketTickResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type MarketHookState =
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: MarketTickResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useMarket() {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<MarketHookState>({ status: "LOADING", data: null, error: null });

  const fetchMarket = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setState({ status: "ERROR", data: null, error: "Not authenticated" });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    try {
      const data = await marketApi.getTick(token);
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load market tick";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, [token, isAuthenticated]);

  useEffect(() => { void fetchMarket(); }, [fetchMarket]);

  return { ...state, refetch: fetchMarket };
}
