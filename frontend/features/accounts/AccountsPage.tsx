"use client";
/** Accounts page — real API with Create Account form. */
import { useState } from "react";
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { useAccounts } from "@/lib/hooks/useAccounts";
import { CreateAccountForm } from "./CreateAccountForm";

export function AccountsPage() {
  const { accounts, loading, error, createAccount, refetch } = useAccounts();
  const [showCreate, setShowCreate] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Accounts</h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">Trading account management. Credentials never stored client-side.</p>
        </div>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="px-3 py-1.5 bg-aurexis-accent hover:bg-aurexis-accent/80 text-black text-2xs font-mono uppercase tracking-wider rounded transition-colors"
        >
          {showCreate ? "Cancel" : "+ Add Account"}
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
            <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
          </div>
        ) : error ? (
          <div className="px-4 py-8 text-center">
            <p className="text-2xs font-mono text-aurexis-danger">{error}</p>
          </div>
        ) : accounts.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <p className="text-xs text-aurexis-subtle">No registered accounts.</p>
            <p className="text-2xs text-aurexis-faint mt-1">Click &ldquo;+ Add Account&rdquo; above to register your first MT5 trading account.</p>
          </div>
        ) : (
          <div className="divide-y divide-aurexis-border/40">
            {accounts.map((acc) => (
              <div key={acc.id} className="px-4 py-3">
                <div className="flex items-center justify-between py-2">
                  <div>
                    <p className="text-xs font-medium text-aurexis-text">{acc.label}</p>
                    <p className="text-2xs text-aurexis-faint font-mono mt-0.5">{acc.broker} · {acc.broker_currency}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {acc.is_cent_account && <Badge variant="info">CENT</Badge>}
                    <Badge variant={acc.is_active ? "success" : "danger"}>
                      {acc.is_active ? "ACTIVE" : "INACTIVE"}
                    </Badge>
                  </div>
                </div>
                <div className="mt-2 pt-2 border-t border-aurexis-border/50">
                  <StatRow label="Account ID"     value={<span className="font-mono text-2xs text-aurexis-subtle">{acc.id}</span>} />
                  <StatRow label="Account No."    value={<span className="font-mono text-aurexis-faint">{acc.mt5_account_number}</span>} />
                  {acc.mt5_server && <StatRow label="Server"         value={<span className="font-mono text-aurexis-faint">{acc.mt5_server}</span>} />}
                  <StatRow label="Normalization"  value={`×${acc.cent_normalization_factor}`} />
                  <StatRow label="Trading"        value={acc.trading_enabled ? <Badge variant="success">ENABLED</Badge> : <Badge variant="warning">DISABLED</Badge>} />
                  <StatRow label="Created"        value={new Date(acc.created_at).toLocaleDateString()} />
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>

      <div className="bg-aurexis-surface border border-aurexis-border/50 rounded px-4 py-3">
        <p className="text-2xs text-aurexis-faint">Broker credentials are never stored in browser storage. Account numbers are treated as opaque identifiers.</p>
      </div>
    </div>
  );
}
