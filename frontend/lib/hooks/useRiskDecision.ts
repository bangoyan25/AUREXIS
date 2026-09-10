"use client";
/**
 * useRiskDecision — GET /api/v1/risk/{accountId}/decision. Auth required. Account-scoped.
 * Returns authoritative server-side Risk Gate decision (ALLOW / BLOCK), reason_code, reason, and details.
 * Polled every 2s while account is active.
 */
import { useState, useEffect, useCallback } from "react";
import { riskApi, type RiskDecisionResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type RiskDecisionHookState =
  | { status: "NO_ACCOUNT"; data: null; error: null }
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: RiskDecisionResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useRiskDecision(accountId: string | null) {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<RiskDecisionHookState>({
    status: "NO_ACCOUNT",
    data: null,
    error: null,
  });

  const fetchDecision = useCallback(async () => {
    if (!token || !isAuthenticated || !accountId) {
      setState({ status: "NO_ACCOUNT", data: null, error: null });
      return;
    }
    try {
      const data = await riskApi.getDecision(accountId, token);
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load risk decision";
      setState((prev) => (prev.status === "OK" ? prev : { status: "ERROR", data: null, error: msg }));
    }
  }, [token, isAuthenticated, accountId]);

  useEffect(() => {
    if (!token || !isAuthenticated || !accountId) {
      setState({ status: "NO_ACCOUNT", data: null, error: null });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    void fetchDecision();

    const interval = setInterval(() => {
      void fetchDecision();
    }, 2000);

    return () => clearInterval(interval);
  }, [fetchDecision, token, isAuthenticated, accountId]);

  return { ...state, refetch: fetchDecision };
}
