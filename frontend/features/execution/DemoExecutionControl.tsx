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
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [volume, setVolume] = useState<number>(0.01);
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
  const isLiveTrading = selectedAccount?.trading_enabled ?? false;

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
      const clientOrderId = `trade-${side.toLowerCase()}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const res = await demoExecutionApi.execute(
        selectedAccountId,
        {
          action: "OPEN_POSITION",
          symbol: "XAUUSD",
          side: side,
          volume: volume,
          client_order_id: clientOrderId,
          comment: isLiveTrading ? "AUREXIS_LIVE" : "AUREXIS_TEST",
        },
        token,
      );
      setExecResult(res);
      await fetchPositions();
      await fetchRiskGate();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal mengeksekusi order";
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
      const clientOrderId = `close-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const res = await demoExecutionApi.execute(
        selectedAccountId,
        {
          action: "CLOSE_POSITION",
          symbol: "XAUUSD",
          position_ticket: ticket,
          client_order_id: clientOrderId,
          comment: isLiveTrading ? "AUREXIS_LIVE_CLOSE" : "AUREXIS_TEST_CLOSE",
        },
        token,
      );
      setExecResult(res);
      await fetchPositions();
      await fetchRiskGate();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal menutup posisi";
      setActionError(msg);
    } finally {
      setClosing(false);
    }
  };

  const isRiskAllow = riskGate?.decision === "ALLOW";

  return (
    <Panel title="Trade Execution Control (MT5 Live & Demo)">
      <div className="p-4 space-y-4">
        {/* Status Mode Banner */}
        <div
          className={`flex items-center justify-between rounded p-3 border ${
            isLiveTrading
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
              : "bg-amber-500/10 border-amber-500/30 text-amber-300"
          }`}
        >
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-0.5 text-2xs font-mono font-bold rounded ${
                isLiveTrading ? "bg-emerald-500 text-black" : "bg-amber-500 text-black"
              }`}
            >
              {isLiveTrading ? "LIVE TRADING AKTIF" : "DEMO / TEST MODE"}
            </span>
            <p className="text-xs font-medium">
              {isLiveTrading
                ? "Akun diotorisasi untuk eksekusi order live ke broker riil."
                : "Akun dalam mode demo/dry-run. Aktifkan Live Trading di menu Accounts."}
            </p>
          </div>
          <div className="text-2xs font-mono text-aurexis-faint">
            Simbol: XAUUSD | Batas Uji: 0.10 Lot
          </div>
        </div>

        {/* Account & Risk info */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-aurexis-surface p-3 rounded border border-aurexis-border text-xs">
          <div>
            <label className="text-2xs text-aurexis-faint uppercase block mb-1">Pilih Akun</label>
            {accountsLoading ? (
              <span className="text-2xs font-mono text-aurexis-faint">Memuat...</span>
            ) : accounts.length === 0 ? (
              <span className="text-2xs text-aurexis-danger">Tidak ada akun</span>
            ) : (
              <select
                value={selectedAccountId}
                onChange={(e) => setSelectedAccountId(e.target.value)}
                className="w-full bg-aurexis-muted border border-aurexis-border text-xs text-aurexis-text rounded px-2 py-1 font-mono"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label} ({a.broker}) — {a.trading_enabled ? "LIVE" : "DEMO"}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div>
            <span className="text-2xs text-aurexis-faint uppercase block mb-1">Broker / Server</span>
            <span className="font-mono text-aurexis-subtle">
              {selectedAccount ? `${selectedAccount.broker} / ${selectedAccount.mt5_server || "Default"}` : "—"}
            </span>
          </div>
          <div>
            <span className="text-2xs text-aurexis-faint uppercase block mb-1">Status Otorisasi</span>
            <span
              className={`font-mono font-semibold ${
                isLiveTrading ? "text-aurexis-success" : "text-aurexis-warning"
              }`}
            >
              {isLiveTrading ? "Live Execution Allowed" : "Dry-Run Only"}
            </span>
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

        {/* Order Parameters */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-aurexis-surface/50 p-3 rounded border border-aurexis-border/60 text-xs">
          <div>
            <label className="text-2xs text-aurexis-faint uppercase block mb-1">Arah Order (Side)</label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setSide("BUY")}
                className={`flex-1 py-1.5 rounded font-mono text-2xs font-semibold uppercase transition-colors ${
                  side === "BUY"
                    ? "bg-emerald-600 text-white shadow-sm"
                    : "bg-aurexis-surface border border-aurexis-border text-aurexis-subtle hover:text-white"
                }`}
              >
                BUY
              </button>
              <button
                type="button"
                onClick={() => setSide("SELL")}
                className={`flex-1 py-1.5 rounded font-mono text-2xs font-semibold uppercase transition-colors ${
                  side === "SELL"
                    ? "bg-rose-600 text-white shadow-sm"
                    : "bg-aurexis-surface border border-aurexis-border text-aurexis-subtle hover:text-white"
                }`}
              >
                SELL
              </button>
            </div>
          </div>

          <div>
            <label className="text-2xs text-aurexis-faint uppercase block mb-1">Volume (Lots)</label>
            <select
              value={volume}
              onChange={(e) => setVolume(parseFloat(e.target.value))}
              className="w-full bg-aurexis-muted border border-aurexis-border text-xs text-aurexis-text rounded px-2.5 py-1.5 font-mono"
            >
              <option value={0.01}>0.01 Lot</option>
              <option value={0.02}>0.02 Lot</option>
              <option value={0.05}>0.05 Lot</option>
              <option value={0.10}>0.10 Lot (Max Test)</option>
            </select>
          </div>

          <div>
            <label className="text-2xs text-aurexis-faint uppercase block mb-1">Instrumen</label>
            <input
              type="text"
              disabled
              value="XAUUSD (Gold)"
              className="w-full bg-aurexis-muted/60 border border-aurexis-border text-xs text-aurexis-faint rounded px-2.5 py-1.5 font-mono"
            />
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
            <span>
              Saya mengonfirmasi eksekusi order {side} {volume} Lot XAUUSD ke terminal MT5 agent.
            </span>
          </label>

          <button
            type="button"
            onClick={handleOpenTrade}
            disabled={!confirmed || !isRiskAllow || executing || openPositions.length > 0}
            className={`px-5 py-2 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-mono font-bold rounded uppercase tracking-wider transition-colors shadow-sm ${
              side === "BUY" ? "bg-emerald-600 hover:bg-emerald-500" : "bg-rose-600 hover:bg-rose-500"
            }`}
          >
            {executing
              ? "Mengeksekusi..."
              : `Eksekusi ${side} (${volume} Lot)`}
          </button>
        </div>

        {openPositions.length > 0 && (
          <div className="mt-4 p-3 bg-emerald-950/20 border border-emerald-500/30 rounded space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold text-emerald-400 uppercase">
                Posisi Terbuka di MT5
              </span>
              <span className="text-2xs font-mono text-aurexis-faint">Jumlah: {openPositions.length}</span>
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
                  {closing ? "Menutup..." : "Close Posisi"}
                </button>
              </div>
            ))}
          </div>
        )}

        {execResult && (
          <div className="mt-3 p-3 bg-aurexis-muted/40 border border-aurexis-border rounded text-2xs font-mono space-y-1">
            <div className="flex items-center justify-between text-aurexis-subtle font-bold">
              <span>Hasil Eksekusi: {execResult.action}</span>
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
