"use client";

import { useState, useEffect, useCallback } from "react";
import { Panel, Badge } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth-context";
import { useAccounts } from "@/lib/hooks/useAccounts";
import {
  demoExecutionApi,
  riskApi,
  type RiskDecisionResponse,
  type TestExecutionResult,
} from "@/lib/api";

export function DemoExecutionControl() {
  const { token } = useAuth();
  const { accounts, loading: accountsLoading } = useAccounts();

  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [riskGate, setRiskGate] = useState<RiskDecisionResponse | null>(null);
  const [riskLoading, setRiskLoading] = useState<boolean>(false);
  const [confirmed, setConfirmed] = useState<boolean>(false);
  const [executing, setExecuting] = useState<boolean>(false);
  const [closing, setClosing] = useState<boolean>(false);
  const [execResult, setExecResult] = useState<TestExecutionResult | null>(null);
  const [openPositions, setOpenPositions] = useState<Array<{
    id: string;
    broker_ticket: number;
    symbol: string;
    side: string;
    lots: string;
    open_price: string;
    status: string;
  }>>([]);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (accounts.length > 0 && accounts[0] && !selectedAccountId) {
      setSelectedAccountId(accounts[0].id);
    }
  }, [accounts, selectedAccountId]);

  const selectedAccount = accounts.find((a) => a.id === selectedAccountId);

  const fetchRiskGate = useCallback(async () => {
    if (!token || !selectedAccountId) return;
    setRiskLoading(true);
    try {
      const res = await riskApi.getDecision(selectedAccountId, token);
      setRiskGate(res);
    } catch {
      setRiskGate(null);
    } finally {
      setRiskLoading(false);
    }
  }, [token, selectedAccountId]);

  const fetchPositions = useCallback(async () => {
    if (!token || !selectedAccountId) return;
    try {
      const res = await demoExecutionApi.getPositions(selectedAccountId, token);
      setOpenPositions(res.positions.filter((p) => p.status === "OPEN"));
    } catch {
      setOpenPositions([]);
    }
  }, [token, selectedAccountId]);

  useEffect(() => {
    void fetchRiskGate();
    void fetchPositions();
    const timer = setInterval(() => {
      void fetchRiskGate();
      void fetchPositions();
    }, 3000);
    return () => clearInterval(timer);
  }, [fetchRiskGate, fetchPositions]);

  const handleOpenTrade = async () => {
    if (!token || !selectedAccountId || !confirmed) return;
    setExecuting(true);
    setActionError(null);
    try {
      const clientOrderId = `test-open-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const res = await demoExecutionApi.execute(
        selectedAccountId,
        {
          action: "OPEN_POSITION",
          symbol: "XAUUSD",
          side: "BUY",
          volume: 0.01,
          client_order_id: clientOrderId,
          comment: "AUREXIS_DEMO_TEST",
        },
        token,
      );
      setExecResult(res);
      await fetchPositions();
      await fetchRiskGate();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute test trade";
      setActionError(msg);
    } finally {
      setExecuting(false);
    }
  };

  const handleClosePosition = async (ticket: number) => {
    if (!token || !selectedAccountId) return;
    setClosing(true);
    setActionError(null);
    try {
      const clientOrderId = `test-close-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const res = await demoExecutionApi.execute(
        selectedAccountId,
        {
          action: "CLOSE_POSITION",
          symbol: "XAUUSD",
          position_ticket: ticket,
          client_order_id: clientOrderId,
          comment: "AUREXIS_DEMO_CLOSE",
        },
        token,
      );
      setExecResult(res);
      await fetchPositions();
      await fetchRiskGate();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to close test position";
      setActionError(msg);
    } finally {
      setClosing(false);
    }
  };

  const isRiskAllow = riskGate?.decision === "ALLOW";

  return (
    <Panel title="Demo Test Execution (Phase 4A MVP)">
      <div className="p-4 space-y-4">
        {/* DEMO ONLY banner */}
        <div className="flex items-center justify-between bg-amber-500/10 border border-amber-500/30 rounded p-3">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 text-2xs font-mono font-bold bg-amber-500 text-black rounded">
              DEMO ONLY
            </span>
            <p className="text-xs text-amber-300 font-medium">
              Controlled single test trade execution pipeline. Live trading disabled.
            </p>
          </div>
          <div className="text-2xs font-mono text-aurexis-faint">
            Max: 0.10 lots | Symbol: XAUUSD
          </div>
        </div>

        {/* Account & Risk info */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-aurexis-surface p-3 rounded border border-aurexis-border text-xs">
          <div>
            <label className="text-2xs text-aurexis-faint uppercase block mb-1">Account</label>
            {accountsLoading ? (
              <span className="text-2xs font-mono text-aurexis-faint">Loading...</span>
            ) : accounts.length === 0 ? (
              <span className="text-2xs text-aurexis-danger">No accounts</span>
            ) : (
              <select
                value={selectedAccountId}
                onChange={(e) => setSelectedAccountId(e.target.value)}
                className="w-full bg-aurexis-muted border border-aurexis-border text-xs text-aurexis-text rounded px-2 py-1 font-mono"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label} ({a.broker})
                  </option>
                ))}
              </select>
            )}
          </div>
          <div>
            <span className="text-2xs text-aurexis-faint uppercase block mb-1">Broker / Server</span>
            <span className="font-mono text-aurexis-subtle">
              {selectedAccount ? `${selectedAccount.broker} / ${selectedAccount.mt5_server || "Demo"}` : "—"}
            </span>
          </div>
          <div>
            <span className="text-2xs text-aurexis-faint uppercase block mb-1">Trade Parameters</span>
            <span className="font-mono text-aurexis-subtle">XAUUSD | 0.01 Lots</span>
          </div>
          <div>
            <span className="text-2xs text-aurexis-faint uppercase block mb-1">Server Risk Gate</span>
            {riskLoading && !riskGate ? (
              <span className="text-2xs font-mono text-aurexis-faint animate-pulse">Checking...</span>
            ) : riskGate ? (
              <div className="flex items-center gap-1.5">
                <Badge variant={riskGate.decision === "ALLOW" ? "success" : "danger"}>
                  {riskGate.decision}
                </Badge>
                <span className="text-2xs font-mono text-aurexis-faint">({riskGate.reason_code})</span>
              </div>
            ) : (
              <span className="text-2xs text-aurexis-faint">Offline</span>
            )}
          </div>
        </div>

        {actionError && (
          <div className="bg-aurexis-danger/10 border border-aurexis-danger/30 rounded p-2.5 text-xs text-aurexis-danger font-mono">
            {actionError}
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-2 border-t border-aurexis-border/50">
          <label className="flex items-center gap-2 cursor-pointer text-xs text-aurexis-subtle select-none">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="rounded border-aurexis-border bg-aurexis-muted text-aurexis-accent focus:ring-0"
            />
            <span>I confirm this is a controlled test trade on a verified MT5 DEMO account.</span>
          </label>

          <button
            type="button"
            onClick={handleOpenTrade}
            disabled={!confirmed || !isRiskAllow || executing || openPositions.length > 0}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-mono font-medium rounded uppercase tracking-wider transition-colors shadow-sm"
          >
            {executing ? "Dispatching..." : "Execute Test Buy (0.01 Lot)"}
          </button>
        </div>

        {openPositions.length > 0 && (
          <div className="mt-4 p-3 bg-emerald-950/20 border border-emerald-500/30 rounded space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold text-emerald-400 uppercase">
                Active Demo Test Position
              </span>
              <span className="text-2xs font-mono text-aurexis-faint">Count: {openPositions.length}</span>
            </div>
            {openPositions.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between p-2 bg-aurexis-surface rounded border border-aurexis-border/60 text-xs font-mono"
              >
                <div>
                  <span className="font-bold text-aurexis-text">Ticket #{p.broker_ticket}</span>
                  <span className="text-aurexis-faint ml-2">
                    {p.symbol} {p.side} {p.lots} @ {p.open_price}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleClosePosition(p.broker_ticket)}
                  disabled={closing}
                  className="px-3 py-1 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-2xs font-mono rounded uppercase tracking-wider transition-colors"
                >
                  {closing ? "Closing..." : "Close Test Position"}
                </button>
              </div>
            ))}
          </div>
        )}

        {execResult && (
          <div className="mt-3 p-3 bg-aurexis-muted/40 border border-aurexis-border rounded text-2xs font-mono space-y-1">
            <div className="flex items-center justify-between text-aurexis-subtle font-bold">
              <span>Last Execution: {execResult.action}</span>
              <Badge variant={execResult.status === "COMPLETED" ? "success" : "danger"}>
                {execResult.status}
              </Badge>
            </div>
            <div className="text-aurexis-faint">Command ID: {execResult.command_id}</div>
            <div className="text-aurexis-faint">Client Order ID: {execResult.client_order_id}</div>
            {execResult.broker_result && (
              <pre className="p-2 bg-black/40 rounded text-emerald-300 overflow-x-auto text-2xs">
                {JSON.stringify(execResult.broker_result, null, 2)}
              </pre>
            )}
            {execResult.error_message && (
              <div className="text-aurexis-danger font-medium">Error: {execResult.error_message}</div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}

