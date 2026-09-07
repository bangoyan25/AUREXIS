"use client";
/**
 * usePositions — GET /api/v1/positions. Auth required.
 * Preserves backend state (e.g. status: EMPTY, positions: []).
 */
import { useState, useEffect, useCallback } from "react";
import { positionsApi, type PositionsResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type PositionsHookState =
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: PositionsResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function usePositions() {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<PositionsHookState>({ status: "LOADING", data: null, error: null });

  const fetchPositions = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setState({ status: "ERROR", data: null, error: "Not authenticated" });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    try {
      const data = await positionsApi.list(token);
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load positions";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, [token, isAuthenticated]);

  useEffect(() => { void fetchPositions(); }, [fetchPositions]);

  return { ...state, refetch: fetchPositions };
}
