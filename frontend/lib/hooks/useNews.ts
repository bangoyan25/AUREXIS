"use client";
/**
 * useNews — GET /api/v1/news. Auth required.
 * Preserves backend state (e.g. status: UNKNOWN, provider: null).
 * UNKNOWN is NOT treated as CLEAR. Fail-closed semantics preserved.
 */
import { useState, useEffect, useCallback } from "react";
import { newsApi, type NewsResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type NewsHookState =
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: NewsResponse; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useNews() {
  const { token, isAuthenticated } = useAuth();
  const [state, setState] = useState<NewsHookState>({ status: "LOADING", data: null, error: null });

  const fetchNews = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setState({ status: "ERROR", data: null, error: "Not authenticated" });
      return;
    }
    setState({ status: "LOADING", data: null, error: null });
    try {
      const data = await newsApi.getState(token);
      // UNKNOWN ≠ CLEAR — preserve backend state exactly
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load news state";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, [token, isAuthenticated]);

  useEffect(() => { void fetchNews(); }, [fetchNews]);

  return { ...state, refetch: fetchNews };
}
