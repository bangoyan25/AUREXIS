"use client";

import { useState } from "react";
import { Panel } from "@/components/ui/primitives";

interface CreateAccountFormProps {
  onCreated: () => void;
  onCancel: () => void;
  createAccount: (body: object) => Promise<unknown>;
}

export function CreateAccountForm({ onCreated, onCancel, createAccount }: CreateAccountFormProps) {
  const [label, setLabel] = useState("");
  const [broker, setBroker] = useState("HFM");
  const [accountNumber, setAccountNumber] = useState("");
  const [server, setServer] = useState("HFMarketsSV-Live");
  const [currency, setCurrency] = useState("USD");
  const [isCent, setIsCent] = useState(false);
  const [factor, setFactor] = useState("1.0");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleBrokerChange = (newBroker: string) => {
    setBroker(newBroker);
    if (newBroker === "HFM") {
      setServer("HFMarketsSV-Live");
    } else if (newBroker === "Exness") {
      setServer("Exness-Real");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!label.trim() || !broker.trim() || !accountNumber.trim()) {
      setError("Label, broker, and MT5 account number are required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await createAccount({
        label: label.trim(),
        broker: broker.trim(),
        mt5_account_number: accountNumber.trim(),
        mt5_server: server.trim() || null,
        broker_currency: currency.trim() || "USD",
        is_cent_account: isCent,
        cent_normalization_factor: isCent ? "0.01" : factor,
      });
      onCreated();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to register account");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel title="Register MT5 Trading Account">
      <form onSubmit={handleSubmit} className="p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">Label *</label>
            <input type="text" required placeholder="e.g. Primary MT5 Live" value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              maxLength={100} />
          </div>
          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">Supported Broker *</label>
            <select
              value={broker}
              onChange={(e) => handleBrokerChange(e.target.value)}
              className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
            >
              <option value="HFM">HFM (HF Markets)</option>
              <option value="Exness">Exness</option>
            </select>
          </div>
          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">MT5 Account Number *</label>
            <input type="text" required placeholder="e.g. 10928374" value={accountNumber}
              onChange={(e) => setAccountNumber(e.target.value)}
              className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              maxLength={50} />
          </div>
          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">MT5 Server</label>
            <input type="text" placeholder="e.g. Broker-Live / MetaQuotes-Demo" value={server}
              onChange={(e) => setServer(e.target.value)}
              className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              maxLength={200} />
          </div>
          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">Currency</label>
            <input type="text" value={currency} onChange={(e) => setCurrency(e.target.value)}
              className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              maxLength={20} />
          </div>
          <div className="flex items-center gap-3 pt-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={isCent}
                onChange={(e) => { setIsCent(e.target.checked); setFactor(e.target.checked ? "0.01" : "1.0"); }}
                className="accent-aurexis-accent" />
              <span className="text-2xs font-mono text-aurexis-subtle">Cent account (factor x0.01)</span>
            </label>
          </div>
        </div>
        {error && (
          <div className="p-2 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded font-mono text-2xs text-aurexis-danger">{error}</div>
        )}
        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={submitting}
            className="px-4 py-1.5 bg-aurexis-accent hover:bg-aurexis-accent/80 text-black text-2xs font-mono uppercase tracking-wider rounded transition-colors disabled:opacity-50">
            {submitting ? "Registering..." : "Register Account"}
          </button>
          <button type="button" onClick={onCancel}
            className="px-4 py-1.5 bg-aurexis-surface border border-aurexis-border text-aurexis-subtle text-2xs font-mono uppercase tracking-wider rounded hover:text-aurexis-text transition-colors">
            Cancel
          </button>
        </div>
        <p className="text-2xs text-aurexis-faint pt-1">
          Broker password is never stored or requested here. Account pairs with MT5 EA via Agent registration.
        </p>
      </form>
    </Panel>
  );
}
