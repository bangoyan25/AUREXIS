"use client";
/**
 * useBrain — GET /api/v1/brain/{accountId}. Auth required. Account-scoped.
 * If accountId is null, no request is made.
 * Backend state preserved: NOT_CONFIGURED → NOT_CONFIGURED.
 */
import { useState, useEffect, useCallback } from "react";
import { brainApi, type BrainStateResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type BrainHookState =
  | { status: "NO_ACCOUNT"; data: null; error: null }
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: BrainStateResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useBrain(accountId: string | null) {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<BrainHookState>({ status: "NO_ACCOUNT", data: null, error: null });

  const fetchBrain = useCallback(async () => {
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
      const data = await brainApi.getState(accountId, token);
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load brain state";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, [token, isAuthenticated, accountId]);

  useEffect(() => { void fetchBrain(); }, [fetchBrain]);

  return { ...state, refetch: fetchBrain };
}
