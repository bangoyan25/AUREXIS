"use client";
/**
 * Exposure Management — Real-time Position Sizing, Margin & Account Utilization.
 */
import { useEffect, useState } from "react";
import { Panel, StatRow, Badge, EmptyState } from "@/components/ui/primitives";
import { useSelectedAccount } from "@/lib/account-context";
import { useAuth } from "@/lib/auth-context";
import { demoExecutionApi } from "@/lib/api";

interface PositionRecord {
  id: string;
  broker_ticket: number;
  symbol: string;
  side: string;
  lots: string;
  open_price: string;
  status: string;
  opened_at: string | null;
}

export function ExposurePage() {
  const { selectedAccountId, selectedAccount } = useSelectedAccount();
  const { token } = useAuth();
  const [positions, setPositions] = useState<PositionRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!token || !selectedAccountId) {
      setLoading(false);
      return;
    }
    demoExecutionApi
      .getPositions(selectedAccountId, token)
      .then((res) => {
        if (res && res.positions) {
          setPositions(res.positions);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token, selectedAccountId]);

  const openList = positions.filter((p) => p.status === "OPEN");
  const totalOpenLots = openList.reduce((sum, p) => sum + parseFloat(p.lots || "0"), 0);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Exposure Management
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Real-time margin allocation, position sizing & aggregate basket exposure controls.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="accent">MAX 1 POSITION</Badge>
          <Badge variant="success">LOT CAP: 0.05 LOTS</Badge>
        </div>
      </div>

      {/* Exposure KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-aurexis-surface border border-aurexis-border rounded p-3.5">
          <span className="text-3xs uppercase tracking-wider text-aurexis-faint block font-mono">
            TOTAL ACTIVE LOTS
          </span>
          <span className="text-xl font-financial font-semibold text-aurexis-text">
            {totalOpenLots.toFixed(2)} lots
          </span>
          <span className="text-3xs text-aurexis-faint block mt-1">
            Limit: 0.05 lots max basket
          </span>
        </div>

        <div className="bg-aurexis-surface border border-aurexis-border rounded p-3.5">
          <span className="text-3xs uppercase tracking-wider text-aurexis-faint block font-mono">
            ACTIVE POSITIONS
          </span>
          <span className="text-xl font-financial font-semibold text-aurexis-text">
            {openList.length} / 1
          </span>
          <span className="text-3xs text-aurexis-faint block mt-1">
            Max 1 concurrent trade rule
          </span>
        </div>

        <div className="bg-aurexis-surface border border-aurexis-border rounded p-3.5">
          <span className="text-3xs uppercase tracking-wider text-aurexis-faint block font-mono">
            ACCOUNT MODEL
          </span>
          <span className="text-base font-mono font-semibold text-aurexis-accent mt-0.5 block">
            {selectedAccount?.is_cent_account ? "Cent Account (USD Normalized)" : "Standard USD Account"}
          </span>
          <span className="text-3xs text-aurexis-faint block mt-1">
            Broker: {selectedAccount?.broker ?? "Generic MT5"}
          </span>
        </div>
      </div>

      {/* Exposure Limits Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Basket & Lot Limits">
          <div className="px-4 py-3">
            <StatRow
              label="Instrument Concentration"
              value={<span className="font-mono text-2xs text-aurexis-accent font-semibold">100% XAUUSD (Single Instrument Scope)</span>}
            />
            <StatRow
              label="Max Concurrent Trades"
              value={<span className="font-mono text-2xs font-semibold text-aurexis-text">1 Open Trade</span>}
            />
            <StatRow
              label="Default Lot Sizing"
              value={<span className="font-mono text-2xs">0.01 lots (Configurable in Settings)</span>}
            />
            <StatRow
              label="Risk-Adjusted Sizing"
              value={<span className="font-mono text-2xs text-aurexis-success">1.0% Account Equity</span>}
            />
            <StatRow
              label="Cent Conversion Factor"
              value={<span className="font-mono text-2xs">10,000 cents = $100 USD (100:1)</span>}
            />
          </div>
        </Panel>

        <Panel title="Open Position Exposure">
          {loading ? (
            <div className="px-4 py-8 text-center text-aurexis-faint font-mono text-xs animate-pulse">
              SYNCING BROKER POSITIONS...
            </div>
          ) : openList.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="Zero Market Exposure"
                description="No active open positions. Margin is 100% available and capital is protected."
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-aurexis-border bg-aurexis-bg/30">
                    <th className="px-4 py-2 text-left text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">Ticket</th>
                    <th className="px-4 py-2 text-left text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">Side</th>
                    <th className="px-4 py-2 text-left text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">Volume</th>
                    <th className="px-4 py-2 text-left text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">Open Price</th>
                  </tr>
                </thead>
                <tbody>
                  {openList.map((p) => (
                    <tr key={p.id} className="border-b border-aurexis-border/40">
                      <td className="px-4 py-2 font-mono text-aurexis-faint text-2xs">#{p.broker_ticket}</td>
                      <td className="px-4 py-2">
                        <Badge variant={p.side === "BUY" ? "success" : "danger"}>{p.side}</Badge>
                      </td>
                      <td className="px-4 py-2 font-mono">{parseFloat(p.lots).toFixed(2)} lots</td>
                      <td className="px-4 py-2 font-mono tabular-nums">{parseFloat(p.open_price).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      {/* Safety Protocol Card */}
      <div className="bg-aurexis-surface border border-aurexis-border/60 rounded p-4 text-2xs font-mono text-aurexis-faint space-y-1.5">
        <div className="flex items-center gap-2 text-aurexis-accent font-semibold uppercase tracking-wider">
          <span>Anti-Martingale Invariant</span>
        </div>
        <p className="leading-relaxed">
          The system strictly forbids revenge trading, uncontrolled averaging down, or implicit martingale lot multiplication. Sizing is governed by the percentage-of-equity model and locked within the authorized 0.05 basket lot ceiling.
        </p>
      </div>
    </div>
  );
}
