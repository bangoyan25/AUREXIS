"use client";

import { useState, useEffect } from "react";
import { Panel } from "@/components/ui/primitives";
import { accountsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface CreateAccountFormProps {
  onCreated: () => void;
  onCancel: () => void;
  createAccount: (body: object) => Promise<unknown>;
}

const DEFAULT_BROKERS = [
  {
    id: "HFM",
    name: "HFM (HF Markets)",
    servers: [
      "HFMarketGlobal-Demo4",
      "HFMarketsGlobal-Demo",
      "HFMarketsGlobal-Demo2",
      "HFMarketsGlobal-Demo3",
      "HFMarketsGlobal-Live",
      "HFMarketsGlobal-Live2",
      "HFMarketsGlobal-Live3",
      "HFMarketsSV-Live",
      "HFMarketsSV-Live2",
      "HFMarketsSV-Live3",
      "HFMarketsSV-Live4",
      "HFMarketsSV-Live5",
      "HFMarketsSV-Live6",
      "HFMarketsSV-Live7",
      "HFMarketsSV-Demo",
      "HFMarketsSA-Live",
      "HFMarketsSA-Demo",
      "HFMarketsEurope-Live",
      "HFMarketsEurope-Demo",
      "HFM-Live",
      "HFM-Demo",
    ],
    currencies: ["USD", "EUR", "GBP", "IDR", "USDCent"],
  },
  {
    id: "Exness",
    name: "Exness",
    servers: [
      "Exness-Real",
      "Exness-Real2",
      "Exness-Real3",
      "Exness-Real4",
      "Exness-Real5",
      "Exness-Real6",
      "Exness-Real7",
      "Exness-Real8",
      "Exness-Real9",
      "Exness-Real10",
      "Exness-Real11",
      "Exness-Real12",
      "Exness-Real13",
      "Exness-Real14",
      "Exness-Real15",
      "Exness-Real16",
      "Exness-Real17",
      "Exness-Real18",
      "Exness-Real19",
      "Exness-Real20",
      "Exness-Real21",
      "Exness-Real22",
      "Exness-Real23",
      "Exness-Real24",
      "Exness-Real25",
      "Exness-Real26",
      "Exness-Real27",
      "Exness-Real28",
      "Exness-Real29",
      "Exness-Real30",
      "Exness-Real31",
      "Exness-Real32",
      "Exness-Real33",
      "Exness-Real34",
      "Exness-Real35",
      "Exness-Real36",
      "Exness-Trial",
      "Exness-Trial2",
      "Exness-Trial3",
      "Exness-Trial4",
      "Exness-Trial5",
      "Exness-Trial6",
      "Exness-Trial7",
      "Exness-Trial8",
      "Exness-Trial9",
      "Exness-Trial10",
    ],
    currencies: ["USD", "EUR", "GBP", "IDR", "USDCent"],
  },
];

export function CreateAccountForm({ onCreated, onCancel, createAccount }: CreateAccountFormProps) {
  const { token } = useAuth();
  const [brokersList, setBrokersList] = useState(DEFAULT_BROKERS);
  const [label, setLabel] = useState("");
  const [broker, setBroker] = useState("HFM");
  const [accountNumber, setAccountNumber] = useState("");
  const [server, setServer] = useState("HFMarketGlobal-Demo4");
  const [customServer, setCustomServer] = useState("");
  const [isCustomServer, setIsCustomServer] = useState(false);
  const [currency, setCurrency] = useState("USD");
  const [customCurrency, setCustomCurrency] = useState("");
  const [isCustomCurrency, setIsCustomCurrency] = useState(false);
  const [isCent, setIsCent] = useState(false);
  const [factor, setFactor] = useState("1.0");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    accountsApi.getBrokers(token)
      .then((data) => {
        if (data && data.length > 0) {
          const merged = data.map((b) => ({
            id: b.id,
            name: b.name,
            servers: b.servers || [],
            currencies: b.currencies || ["USD", "EUR", "GBP", "IDR", "USDCent"],
          }));
          setBrokersList(merged);
        }
      })
      .catch(() => {
        // Fallback to static DEFAULT_BROKERS
      });
  }, [token]);

  const currentBroker = brokersList.find((b) => b.id === broker) || brokersList[0];
  const availableServers = currentBroker?.servers || [];
  const availableCurrencies = currentBroker?.currencies || ["USD", "EUR", "GBP", "IDR", "USDCent"];

  const handleBrokerChange = (newBroker: string) => {
    setBroker(newBroker);
    const bObj = brokersList.find((b) => b.id === newBroker) || brokersList[0];
    if (bObj && bObj.servers.length > 0 && bObj.servers[0]) {
      setServer(bObj.servers[0]);
      setIsCustomServer(false);
    }
  };

  const handleServerChange = (val: string) => {
    if (val === "__CUSTOM__") {
      setIsCustomServer(true);
      setCustomServer("");
    } else {
      setIsCustomServer(false);
      setServer(val);
    }
  };

  const handleCurrencyChange = (val: string) => {
    if (val === "__CUSTOM__") {
      setIsCustomCurrency(true);
      setCustomCurrency("");
    } else {
      setIsCustomCurrency(false);
      setCurrency(val);
      if (val.toLowerCase().includes("cent")) {
        setIsCent(true);
        setFactor("0.01");
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const finalServer = isCustomServer ? customServer.trim() : server.trim();
    const finalCurrency = isCustomCurrency ? customCurrency.trim() : currency.trim();

    if (!label.trim() || !broker.trim() || !accountNumber.trim()) {
      setError("Label, broker, dan nomor akun MT5 wajib diisi.");
      return;
    }
    if (isCustomServer && !customServer.trim()) {
      setError("Nama server MT5 wajib diisi jika memilih custom.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await createAccount({
        label: label.trim(),
        broker: broker.trim(),
        mt5_account_number: accountNumber.trim(),
        mt5_server: finalServer || null,
        broker_currency: finalCurrency || "USD",
        is_cent_account: isCent,
        cent_normalization_factor: isCent ? "0.01" : factor,
      });
      onCreated();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal mendaftarkan akun");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel title="Register MT5 Trading Account">
      <form onSubmit={handleSubmit} className="p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">Label Akun *</label>
            <input
              type="text"
              required
              placeholder="Contoh: Exness Real XAUUSD / HFM Live"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              maxLength={100}
            />
          </div>

          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">Pilih Broker *</label>
            <select
              value={broker}
              onChange={(e) => handleBrokerChange(e.target.value)}
              className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
            >
              {brokersList.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">MT5 Account Number (Login ID) *</label>
            <input
              type="text"
              required
              placeholder="Contoh: 10928374"
              value={accountNumber}
              onChange={(e) => setAccountNumber(e.target.value)}
              className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              maxLength={50}
            />
          </div>

          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">MT5 Server</label>
            {!isCustomServer ? (
              <select
                value={server}
                onChange={(e) => handleServerChange(e.target.value)}
                className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              >
                {availableServers.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
                <option value="__CUSTOM__">[Input Server Lainnya...]</option>
              </select>
            ) : (
              <div className="flex gap-1.5">
                <input
                  type="text"
                  required
                  placeholder="Ketik nama server MT5..."
                  value={customServer}
                  onChange={(e) => setCustomServer(e.target.value)}
                  className="flex-1 bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
                  maxLength={200}
                />
                <button
                  type="button"
                  onClick={() => setIsCustomServer(false)}
                  className="px-2 py-1 bg-aurexis-surface border border-aurexis-border text-3xs font-mono text-aurexis-subtle rounded hover:text-aurexis-text"
                >
                  List
                </button>
              </div>
            )}
          </div>

          <div>
            <label className="block text-2xs font-mono text-aurexis-subtle mb-1">Mata Uang Akun</label>
            {!isCustomCurrency ? (
              <select
                value={currency}
                onChange={(e) => handleCurrencyChange(e.target.value)}
                className="w-full bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              >
                {availableCurrencies.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
                <option value="__CUSTOM__">[Lainnya...]</option>
              </select>
            ) : (
              <div className="flex gap-1.5">
                <input
                  type="text"
                  required
                  placeholder="e.g. USD / EUR / IDR"
                  value={customCurrency}
                  onChange={(e) => setCustomCurrency(e.target.value.toUpperCase())}
                  className="flex-1 bg-aurexis-elevated border border-aurexis-border rounded px-2.5 py-1.5 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
                  maxLength={10}
                />
                <button
                  type="button"
                  onClick={() => setIsCustomCurrency(false)}
                  className="px-2 py-1 bg-aurexis-surface border border-aurexis-border text-3xs font-mono text-aurexis-subtle rounded hover:text-aurexis-text"
                >
                  List
                </button>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3 pt-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isCent}
                onChange={(e) => {
                  setIsCent(e.target.checked);
                  setFactor(e.target.checked ? "0.01" : "1.0");
                }}
                className="accent-aurexis-accent"
              />
              <span className="text-2xs font-mono text-aurexis-subtle">
                Akun Cent (Normalisasi USD faktor x0.01)
              </span>
            </label>
          </div>
        </div>

        {error && (
          <div className="p-2 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded font-mono text-2xs text-aurexis-danger">
            {error}
          </div>
        )}

        <div className="flex gap-2 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="px-4 py-1.5 bg-aurexis-accent hover:bg-aurexis-accent/80 text-black text-2xs font-mono uppercase tracking-wider rounded transition-colors disabled:opacity-50"
          >
            {submitting ? "Mendaftarkan..." : "Daftarkan Akun"}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-1.5 bg-aurexis-surface border border-aurexis-border text-aurexis-subtle text-2xs font-mono uppercase tracking-wider rounded hover:text-aurexis-text transition-colors"
          >
            Batal
          </button>
        </div>
      </form>
    </Panel>
  );
}
