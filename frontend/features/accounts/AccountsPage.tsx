"use client";
/** Accounts page — real API with Create Account form, MT5 Verification, and Live Trading Toggle. */
import { useState } from "react";
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { useAccounts } from "@/lib/hooks/useAccounts";
import { accountsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { CreateAccountForm } from "./CreateAccountForm";

export function AccountsPage() {
  const { accounts, loading, error, createAccount, refetch } = useAccounts();
  const { token } = useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [verifyResults, setVerifyResults] = useState<Record<string, {
    verified: boolean;
    status: string;
    message: string;
    terminal_login?: string;
  }>>({});

  const handleVerifyAgent = async (accountId: string) => {
    if (!token) return;
    setVerifyingId(accountId);
    try {
      const res = await accountsApi.verifyAgent(accountId, token);
      setVerifyResults((prev) => ({
        ...prev,
        [accountId]: res,
      }));
      void refetch();
    } catch (err: unknown) {
      setVerifyResults((prev) => ({
        ...prev,
        [accountId]: {
          verified: false,
          status: "ERROR",
          message: err instanceof Error ? err.message : "Gagal memverifikasi agent",
        },
      }));
    } finally {
      setVerifyingId(null);
    }
  };

  const handleToggleTrading = async (accountId: string, currentEnabled: boolean) => {
    if (!token) return;
    setTogglingId(accountId);
    try {
      await accountsApi.patch(accountId, { trading_enabled: !currentEnabled }, token);
      void refetch();
    } catch {
      // Error handled by refetch
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Trading Accounts</h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Manajemen akun MT5 & Verifikasi koneksi EA live agent.
          </p>
        </div>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="px-3 py-1.5 bg-aurexis-accent hover:bg-aurexis-accent/80 text-black text-2xs font-mono uppercase tracking-wider rounded transition-colors"
        >
          {showCreate ? "Batal" : "+ Tambah Akun"}
        </button>
      </div>

      {showCreate && (
        <CreateAccountForm
          createAccount={createAccount}
          onCreated={() => {
            setShowCreate(false);
            void refetch();
          }}
          onCancel={() => setShowCreate(false)}
        />
      )}

      <Panel title="Registered Accounts">
        {loading ? (
          <div className="px-4 py-8 text-center">
            <span className="text-2xs font-mono text-aurexis-faint animate-pulse">MEMUAT AKUN...</span>
          </div>
        ) : error ? (
          <div className="px-4 py-8 text-center">
            <p className="text-2xs font-mono text-aurexis-danger">{error}</p>
          </div>
        ) : accounts.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-xs text-aurexis-subtle">Belum ada akun MT5 terdaftar.</p>
            <p className="text-2xs text-aurexis-faint mt-1">
              Klik &ldquo;+ Tambah Akun&rdquo; untuk mendaftarkan akun MT5 Exness atau HFM Anda.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-aurexis-border/40">
            {accounts.map((acc) => {
              const vRes = verifyResults[acc.id];
              return (
                <div key={acc.id} className="px-4 py-3">
                  <div className="flex items-center justify-between py-2">
                    <div>
                      <p className="text-xs font-medium text-aurexis-text">{acc.label}</p>
                      <p className="text-2xs text-aurexis-faint font-mono mt-0.5">
                        {acc.broker} · {acc.broker_currency} · Server: {acc.mt5_server || "Default"}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {acc.is_cent_account && <Badge variant="info">CENT</Badge>}
                      <Badge variant={acc.is_active ? "success" : "danger"}>
                        {acc.is_active ? "ACTIVE" : "INACTIVE"}
                      </Badge>
                      <Badge variant={acc.trading_enabled ? "success" : "warning"}>
                        {acc.trading_enabled ? "LIVE TRADING ON" : "TRADING DISABLED"}
                      </Badge>
                    </div>
                  </div>

                  <div className="mt-2 pt-2 border-t border-aurexis-border/50">
                    <StatRow label="Account ID" value={<span className="font-mono text-2xs text-aurexis-subtle">{acc.id}</span>} />
                    <StatRow label="MT5 Account No." value={<span className="font-mono text-aurexis-text font-semibold">{acc.mt5_account_number}</span>} />
                    {acc.mt5_server && <StatRow label="MT5 Server" value={<span className="font-mono text-aurexis-faint">{acc.mt5_server}</span>} />}
                    <StatRow label="Normalisasi USD" value={`×${acc.cent_normalization_factor}`} />
                    <StatRow
                      label="Live Trading State"
                      value={
                        <div className="flex items-center gap-2">
                          <span className={`font-mono text-2xs font-semibold ${acc.trading_enabled ? "text-aurexis-success" : "text-aurexis-warning"}`}>
                            {acc.trading_enabled ? "AKTIF (Bisa Eksekusi Live)" : "NONAKTIF (Dry-Run Only)"}
                          </span>
                          <button
                            onClick={() => handleToggleTrading(acc.id, acc.trading_enabled)}
                            disabled={togglingId === acc.id}
                            className={`px-2 py-0.5 rounded text-3xs font-mono border transition-colors ${
                              acc.trading_enabled
                                ? "border-aurexis-danger/40 text-aurexis-danger hover:bg-aurexis-danger/10"
                                : "border-aurexis-success/40 text-aurexis-success hover:bg-aurexis-success/10"
                            }`}
                          >
                            {togglingId === acc.id ? "..." : acc.trading_enabled ? "Nonaktifkan" : "Aktifkan Live"}
                          </button>
                        </div>
                      }
                    />
                  </div>

                  {/* Verification Section */}
                  <div className="mt-3 pt-2.5 border-t border-aurexis-border/40 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleVerifyAgent(acc.id)}
                        disabled={verifyingId === acc.id}
                        className="px-2.5 py-1 bg-aurexis-surface hover:bg-aurexis-surface/80 border border-aurexis-border rounded text-2xs font-mono text-aurexis-text transition-colors disabled:opacity-50"
                      >
                        {verifyingId === acc.id ? "MEMERIKSA MT5..." : "🔍 Verifikasi MT5 Agent"}
                      </button>

                      {vRes && (
                        <Badge variant={vRes.verified ? "success" : vRes.status === "AGENT_OFFLINE" ? "warning" : "danger"}>
                          {vRes.status}
                        </Badge>
                      )}
                    </div>

                    {vRes && (
                      <p className={`text-2xs font-mono ${vRes.verified ? "text-aurexis-success" : "text-aurexis-warning"}`}>
                        {vRes.message}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
