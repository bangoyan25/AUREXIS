"use client";

import { useState } from "react";
import { Panel } from "@/components/ui/primitives";
import type { AccountResponse } from "@/lib/api";

interface RegisterAgentFormProps {
  accounts: AccountResponse[];
  onRegistered: (result: { account_id: string; label: string; notes?: string | null }) => void;
  onCancel: () => void;
  registering: boolean;
  error: string | null;
}

export function RegisterAgentForm({ accounts, onRegistered, onCancel, registering, error }: RegisterAgentFormProps) {
  const [label, setLabel] = useState("");
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!label.trim()) { setFormError("Label is required."); return; }
    if (!accountId) { setFormError("Select a trading account."); return; }
    setFormError(null);
    onRegistered({ account_id: accountId, label: label.trim(), notes: notes.trim() || null });
  };

  const displayError = error ?? formError;

  return (
    <Panel title="Register MT5 Agent">
      <form onSubmit={handleSubmit} className="p-4 space-y-3">
        {accounts.length === 0 ? (
          <div className="p-3 bg-aurexis-elevated border border-aurexis-border rounded">
            <p className="text-xs font-mono text-aurexis-subtle">
              No trading accounts found. Register a trading account first before creating an agent.
            </p>
          </div>
        ) : (
          <>
            <div>
              <label className="block text-2xs font-mono text-aurexis-subtle mb-1">Trading Account *</label>
              <select
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              >
                {accounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.label} ({acc.broker} · {acc.mt5_account_number})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-2xs font-mono text-aurexis-subtle mb-1">Agent Label *</label>
              <input
                type="text"
                required
                placeholder="e.g. Main EA Executor"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
                maxLength={100}
              />
            </div>

            <div>
              <label className="block text-2xs font-mono text-aurexis-subtle mb-1">Notes (optional)</label>
              <textarea
                placeholder="e.g. Windows VPS — Contabo Germany"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent resize-none"
                rows={2}
                maxLength={2000}
              />
            </div>

            {displayError && (
              <div className="p-2 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded font-mono text-2xs text-aurexis-danger">
                {displayError}
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <button
                type="submit"
                disabled={registering}
                className="px-4 py-1.5 bg-aurexis-accent hover:bg-aurexis-accent/80 text-black text-2xs font-mono uppercase tracking-wider rounded transition-colors disabled:opacity-50"
              >
                {registering ? "Registering..." : "Register Agent"}
              </button>
              <button
                type="button"
                onClick={onCancel}
                className="px-4 py-1.5 bg-aurexis-surface border border-aurexis-border text-aurexis-subtle text-2xs font-mono uppercase tracking-wider rounded hover:text-aurexis-text transition-colors"
              >
                Cancel
              </button>
            </div>

            <p className="text-2xs text-aurexis-faint">
              An agent secret will be generated. It is shown ONCE — save it immediately for MT5 EA configuration.
            </p>
          </>
        )}
      </form>
    </Panel>
  );
}
