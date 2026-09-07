"use client";
/**
 * useRisk — GET /api/v1/risk/{accountId}. Auth required. Account-scoped.
 * If accountId is null, no request is made.
 * Backend state preserved: NOT_CONFIGURED → NOT_CONFIGURED.
 */
import { useState, useEffect, useCallback } from "react";
import { riskApi, type RiskStateResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type RiskHookState =
  | { status: "NO_ACCOUNT"; data: null; error: null }
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: RiskStateResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useRisk(accountId: string | null) {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<RiskHookState>({ status: "NO_ACCOUNT", data: null, error: null });

  const fetchRisk = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setState({ status: "NO_ACCOUNT", data: null, error: null });
      return;
    }
    if (!accountId) {
      setState({ status: "NO_ACCOUNT", data: null, error: null });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    try {
      const data = await riskApi.getState(accountId, token);
      // Preserve backend state exactly — do NOT fabricate values
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load risk state";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, [token, isAuthenticated, accountId]);

  useEffect(() => { void fetchRisk(); }, [fetchRisk]);

  return { ...state, refetch: fetchRisk };
}
