"use client";
/**
 * useHealth — fetches GET /api/v1/health.
 * No auth required. Used by GlobalHeader + SystemPanel.
 */
import { useState, useEffect, useCallback } from "react";
import { healthApi } from "@/lib/api";
import type { SystemHealth } from "@/types/domain";

export type HealthState =
  | { status: "LOADING"; data: null; error: null }
  | { status: "OK"; data: SystemHealth; error: null }
  | { status: "ERROR"; data: null; error: string };

export function useHealth() {
  const [state, setState] = useState<HealthState>({ status: "LOADING", data: null, error: null });

  const fetch = useCallback(async () => {
    setState({ status: "LOADING", data: null, error: null });
    try {
      const data = await healthApi.getHealth();
      setState({ status: "OK", data, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to connect to AUREXIS backend";
      setState({ status: "ERROR", data: null, error: msg });
    }
  }, []);

  useEffect(() => { void fetch(); }, [fetch]);

  return { ...state, refetch: fetch };
}
