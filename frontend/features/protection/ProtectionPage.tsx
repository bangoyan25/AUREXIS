"use client";
/**
 * Dynamic Profit Lock & Capital Protection Engine.
 */
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { useRisk } from "@/lib/hooks/useRisk";
import { useSelectedAccount } from "@/lib/account-context";

export function ProtectionPage() {
  const { selectedAccountId } = useSelectedAccount();
  const { status, data: risk, error } = useRisk(selectedAccountId);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Dynamic Profit Lock & Capital Protection
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Monotonically rising equity protection floor based on session peak profit.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="accent">PCT_RETRACE FORMULA</Badge>
          <Badge variant="success">MONOTONIC RISING FLOOR</Badge>
        </div>
      </div>

      {status === "NO_ACCOUNT" && (
        <div className="bg-aurexis-warning/5 border border-aurexis-warning/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-warning font-medium">NO ACCOUNT SELECTED</p>
        </div>
      )}

      {status === "ERROR" && (
        <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-danger font-medium">CONNECTION ERROR — {error}</p>
        </div>
      )}

      {/* Hero Card: Dynamic Profit Lock State */}
      <div className="bg-aurexis-surface border border-aurexis-border rounded p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex flex-col items-center md:items-start gap-2">
          <span className="text-2xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Dynamic Profit Lock State
          </span>
          <div className="flex items-center gap-3">
            <Badge variant="success">ACTIVE (PROTECTED)</Badge>
            <span className="font-mono text-sm font-semibold text-aurexis-text">
              Locked PCT_RETRACE Architecture
            </span>
          </div>
          <p className="text-xs text-aurexis-subtle max-w-xl leading-relaxed mt-1">
            As session profit increases beyond +$10.00 USD, allowable giveback increases in a controlled manner while a rising floor permanently preserves earned equity.
          </p>
        </div>

        <div className="flex flex-col items-center md:items-end gap-1.5 flex-shrink-0">
          <span className="text-3xs font-mono uppercase tracking-wider text-aurexis-faint">
            CALCULATION BASIS:
          </span>
          <Badge variant="accent">FLOATING_EQUITY</Badge>
          <span className="text-3xs font-mono text-aurexis-faint">
            Reset: UTC 00:00 Daily
          </span>
        </div>
      </div>

      {/* Mathematical Progression Table & Parameters */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Mathematical Progression Model">
          <div className="p-4 space-y-3">
            <p className="text-xs text-aurexis-subtle leading-relaxed">
              Formula: <span className="font-mono font-semibold text-aurexis-accent">Protected_Floor = Peak_Profit - (Peak_Profit × 30%)</span>
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-aurexis-border bg-aurexis-bg/40">
                    <th className="px-3 py-2 text-left text-3xs uppercase text-aurexis-subtle font-medium">Peak Profit</th>
                    <th className="px-3 py-2 text-left text-3xs uppercase text-aurexis-subtle font-medium">Max Drawdown Allowed</th>
                    <th className="px-3 py-2 text-right text-3xs uppercase text-aurexis-subtle font-medium">Protected Floor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-aurexis-border/40 text-2xs">
                  <tr>
                    <td className="px-3 py-2 text-aurexis-text">+$10.00 USD</td>
                    <td className="px-3 py-2 text-aurexis-danger">-$3.00 USD (30%)</td>
                    <td className="px-3 py-2 text-right text-aurexis-success font-semibold">+$7.00 USD</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 text-aurexis-text">+$20.00 USD</td>
                    <td className="px-3 py-2 text-aurexis-danger">-$6.00 USD (30%)</td>
                    <td className="px-3 py-2 text-right text-aurexis-success font-semibold">+$14.00 USD</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 text-aurexis-text">+$50.00 USD</td>
                    <td className="px-3 py-2 text-aurexis-danger">-$15.00 USD (30%)</td>
                    <td className="px-3 py-2 text-right text-aurexis-success font-semibold">+$35.00 USD</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 text-aurexis-text">+$100.00 USD</td>
                    <td className="px-3 py-2 text-aurexis-danger">-$30.00 USD (30%)</td>
                    <td className="px-3 py-2 text-right text-aurexis-success font-semibold">+$70.00 USD</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </Panel>

        <Panel title="Profit Lock Engine Parameters">
          <div className="px-4 py-3">
            <StatRow
              label="Approved Mathematical Formula"
              value={<span className="font-mono text-2xs text-aurexis-accent font-semibold">PCT_RETRACE</span>}
            />
            <StatRow
              label="Activation Milestone"
              value={<span className="font-mono text-2xs text-aurexis-success font-semibold">+$10.00 USD</span>}
            />
            <StatRow
              label="Max Retracement Allowed"
              value={<span className="font-mono text-2xs text-aurexis-text">30.0% of Peak Gain</span>}
            />
            <StatRow
              label="Gain Retention Guaranteed"
              value={<span className="font-mono text-2xs text-aurexis-success font-semibold">70.0% Monotonic Floor</span>}
            />
            <StatRow
              label="Floating Equity Basis"
              value={<Badge variant="success">INCLUDES UNREALIZED PNL</Badge>}
            />
            <StatRow
              label="Drawdown Reference"
              value={<Badge variant="accent">LIFETIME_HWM</Badge>}
            />
          </div>
        </Panel>
      </div>

      {/* Safety Invariant Box */}
      <div className="bg-aurexis-surface border border-aurexis-border/60 rounded p-4 text-2xs font-mono text-aurexis-faint space-y-1.5">
        <div className="flex items-center gap-2 text-aurexis-accent font-semibold uppercase tracking-wider">
          <span>Floor Monotonicity Invariant</span>
        </div>
        <p className="leading-relaxed">
          The protected equity floor is strictly monotonic non-decreasing during a trading session: it can only move UP as new equity peaks are formed, never down. If floating equity pulls back to touch or breach the floor, the system halts new entries and transitions to the `PROTECTED` state immediately.
        </p>
      </div>
    </div>
  );
}
