"use client";
/**
 * useSignals — GET /api/v1/signals. Auth required.
 * Preserves backend state (e.g. status: NOT_CONFIGURED, signals: []).
 */
import { useState, useEffect, useCallback } from "react";
import { signalsApi, type SignalsResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type SignalsHookState =
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: SignalsResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useSignals() {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<SignalsHookState>({ status: "LOADING", data: null, error: null });

  const fetchSignals = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setState({ status: "ERROR", data: null, error: "Not authenticated" });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    try {
      const data = await signalsApi.list(token);
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load signals";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, [token, isAuthenticated]);

  useEffect(() => { void fetchSignals(); }, [fetchSignals]);

  return { ...state, refetch: fetchSignals };
}
