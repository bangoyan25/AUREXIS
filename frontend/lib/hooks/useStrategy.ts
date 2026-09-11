"use client";
/**
 * useStrategy — controls and observability for AUREXIS Strategy Engine (Phase 4B/4C).
 * Provides read state, latest signal, enable, disable, and evaluate triggers.
 */
import { useState, useEffect, useCallback } from "react";
import {
  strategyApi,
  type StrategyStateResponse,
  type LatestSignalResponse,
  type StrategyEvaluateResponse,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type StrategyHookState =
  | { status: "NO_ACCOUNT"; state: null; latestSignal: null; error: null }
  | { status: "LOADING"; state: null; latestSignal: null; error: null }
  | {
      status: "OK";
      state: StrategyStateResponse;
      latestSignal: LatestSignalResponse | null;
      error: null;
    }
  | { status: "ERROR"; state: null; latestSignal: null; error: string };

export function useStrategy(accountId: string | null) {
  const { token, isAuthenticated } = useAuth();
  const [hookState, setHookState] = useState<StrategyHookState>({
    status: "NO_ACCOUNT",
    state: null,
    latestSignal: null,
    error: null,
  });
  const [evaluating, setEvaluating] = useState(false);
  const [evalResult, setEvalResult] = useState<StrategyEvaluateResponse | null>(null);
  const [killSwitchActive, setKillSwitchActive] = useState<boolean>(false);

  const refresh = useCallback(async () => {
    if (!token || !isAuthenticated || !accountId) {
      setHookState({ status: "NO_ACCOUNT", state: null, latestSignal: null, error: null });
      return;
    }
    try {
      const stateData = await strategyApi.getState(accountId, token);
      let sigData: LatestSignalResponse | null = null;
      try {
        sigData = await strategyApi.getLatestSignal(accountId, token);
      } catch {
        sigData = null;
      }
      try {
        const ks = await strategyApi.getKillSwitch(accountId, token);
        setKillSwitchActive(ks.kill_switch_active);
      } catch {
        // non-blocking
      }
      setHookState({
        status: "OK",
        state: stateData,
        latestSignal: sigData,
        error: null,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load strategy state";
      setHookState((prev) =>
        prev.status === "OK" ? prev : { status: "ERROR", state: null, latestSignal: null, error: msg }
      );
    }
  }, [token, isAuthenticated, accountId]);

  useEffect(() => {
    if (!token || !isAuthenticated || !accountId) {
      setHookState({ status: "NO_ACCOUNT", state: null, latestSignal: null, error: null });
      return;
    }
    setHookState({ status: "LOADING", state: null, latestSignal: null, error: null });
    void refresh();

    const interval = setInterval(() => {
      void refresh();
    }, 3000);

    return () => clearInterval(interval);
  }, [refresh, token, isAuthenticated, accountId]);

  const enable = async (dryRun: boolean = true) => {
    if (!token || !accountId) return;
    await strategyApi.enable(accountId, dryRun, token);
    await refresh();
  };

  const disable = async () => {
    if (!token || !accountId) return;
    await strategyApi.disable(accountId, token);
    await refresh();
  };

  const setKillSwitch = async (active: boolean) => {
    if (!token || !accountId) return;
    const res = await strategyApi.setKillSwitch(accountId, active, token);
    setKillSwitchActive(res.kill_switch_active);
    await refresh();
  };

  const evaluate = async () => {
    if (!token || !accountId) return null;
    setEvaluating(true);
    try {
      const res = await strategyApi.evaluate(accountId, token);
      setEvalResult(res);
      await refresh();
      return res;
    } finally {
      setEvaluating(false);
    }
  };

  return {
    ...hookState,
    evaluating,
    evalResult,
    killSwitchActive,
    refresh,
    enable,
    disable,
    setKillSwitch,
    evaluate,
  };
}
