"use client";
/**
 * Risk Center — Authoritative Risk Engine Dashboard, Kill Switch & Parameter Controls.
 */
import { useState, useEffect } from "react";
import { Panel, StatRow, Badge } from "@/components/ui/primitives";
import { RiskStateBadge } from "@/components/ui/badges";
import { useRisk } from "@/lib/hooks/useRisk";
import { useStrategy } from "@/lib/hooks/useStrategy";
import { useSelectedAccount } from "@/lib/account-context";
import { useAuth } from "@/lib/auth-context";
import { strategyApi } from "@/lib/api";

export function RiskCenterPage() {
  const { selectedAccountId } = useSelectedAccount();
  const { token } = useAuth();
  const { status, data: risk, error, refetch: refetchRisk } = useRisk(selectedAccountId);
  const strategy = useStrategy(selectedAccountId);

  const [togglingKillSwitch, setTogglingKillSwitch] = useState<boolean>(false);
  const [killSwitchError, setKillSwitchError] = useState<string | null>(null);

  const isAllowed = risk?.trading_allowed ?? true;
  const isKillSwitchArmed = strategy.killSwitchActive;

  const handleToggleKillSwitch = async () => {
    if (!selectedAccountId || !token) return;
    setTogglingKillSwitch(true);
    setKillSwitchError(null);
    try {
      await strategyApi.setKillSwitch(selectedAccountId, !isKillSwitchArmed, token);
      await strategy.refresh();
      await refetchRisk();
    } catch (err: unknown) {
      setKillSwitchError(err instanceof Error ? err.message : "Failed to toggle kill switch");
    } finally {
      setTogglingKillSwitch(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Risk Center
          </h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">
            Authoritative server-side Risk Engine. Risk Engine authority cannot be bypassed.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={isAllowed && !isKillSwitchArmed ? "success" : "danger"}>
            {isAllowed && !isKillSwitchArmed ? "RISK PERMITTED: ALLOW" : "RISK GATE: BLOCKED"}
          </Badge>
          <Badge variant="accent">RISK-FIRST PHILOSOPHY</Badge>
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

      {killSwitchError && (
        <div className="p-3 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded text-xs text-aurexis-danger font-mono">
          {killSwitchError}
        </div>
      )}

      {/* Hero Card: Primary Risk Decision & Emergency Kill Switch */}
      <div className="bg-aurexis-surface border border-aurexis-border rounded p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex flex-col items-center md:items-start gap-2">
          <span className="text-2xs font-medium uppercase tracking-widest text-aurexis-subtle">
            Authoritative Risk Gate Status
          </span>
          <div className="flex items-center gap-3">
            <RiskStateBadge state={isKillSwitchArmed ? "EMERGENCY_STOP" : isAllowed ? "NORMAL" : "STOPPED"} />
            <span className="font-mono text-sm font-semibold text-aurexis-text">
              {isKillSwitchArmed
                ? "EMERGENCY STOP (KILL SWITCH ARMED)"
                : isAllowed
                ? "ALL RISK CHECKS PASSED (NORMAL)"
                : `ENTRY BLOCKED (${risk?.block_reason || "RISK_LIMIT"})`}
            </span>
          </div>
          <p className="text-xs text-aurexis-subtle max-w-xl leading-relaxed mt-1">
            {isKillSwitchArmed
              ? "Emergency kill switch is armed. All new trade commands are strictly vetoed by the server."
              : risk?.note ||
                "Account equity, open exposure, spread, staleness, and daily loss limits are within authorized boundaries."}
          </p>
        </div>

        {/* Emergency Kill Switch Button */}
        <div className="flex flex-col items-center md:items-end gap-2 flex-shrink-0">
          <span className="text-3xs font-mono uppercase tracking-wider text-aurexis-faint">
            OPERATOR EMERGENCY CONTROL:
          </span>
          <button
            disabled={togglingKillSwitch || !selectedAccountId}
            onClick={handleToggleKillSwitch}
            className={`px-4 py-2 rounded text-xs font-mono font-semibold uppercase tracking-wider transition-colors shadow-sm disabled:opacity-50 ${
              isKillSwitchArmed
                ? "bg-aurexis-success text-aurexis-bg hover:bg-aurexis-success/90"
                : "bg-aurexis-danger text-white hover:bg-aurexis-danger/90"
            }`}
          >
            {togglingKillSwitch
              ? "Updating..."
              : isKillSwitchArmed
              ? "Disarm Kill Switch"
              : "ARM EMERGENCY KILL SWITCH"}
          </button>
          <span className="text-3xs font-mono text-aurexis-faint">
            {isKillSwitchArmed ? "State: SYSTEM HALTED" : "State: ARMED UPON CLICK"}
          </span>
        </div>
      </div>

      {/* Grid: Parameters, Profit Lock, and Execution Limits */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {/* Core Risk Parameters */}
        <Panel title="Locked Risk Parameters">
          <div className="px-4 py-3">
            <StatRow
              label="Daily Loss Limit"
              value={<span className="font-mono text-2xs text-aurexis-text font-semibold">$50.00 USD</span>}
            />
            <StatRow
              label="Max Drawdown"
              value={<span className="font-mono text-2xs text-aurexis-text font-semibold">$100.00 USD</span>}
            />
            <StatRow
              label="Max Open Positions"
              value={<span className="font-mono text-2xs text-aurexis-text font-semibold">1 position</span>}
            />
            <StatRow
              label="Risk Per Trade"
              value={<span className="font-mono text-2xs text-aurexis-accent font-semibold">1.0% Equity</span>}
            />
            <StatRow
              label="Default Lot Size"
              value={<span className="font-mono text-2xs text-aurexis-text">0.01 lots</span>}
            />
            <StatRow
              label="Drawdown Reference"
              value={<Badge variant="accent">LIFETIME_HWM</Badge>}
            />
          </div>
        </Panel>

        {/* Dynamic Profit Lock Panel */}
        <Panel title="Dynamic Profit Lock Engine">
          <div className="px-4 py-3">
            <StatRow
              label="Approved Formula"
              value={<span className="font-mono text-2xs text-aurexis-accent font-semibold">PCT_RETRACE</span>}
            />
            <StatRow
              label="Activation Threshold"
              value={<span className="font-mono text-2xs text-aurexis-success">+$10.00 USD Profit</span>}
            />
            <StatRow
              label="Max Allowable Giveback"
              value={<span className="font-mono text-2xs text-aurexis-text font-semibold">30% of Peak Gain</span>}
            />
            <StatRow
              label="Protected Floor Retention"
              value={<span className="font-mono text-2xs text-aurexis-success font-semibold">70% Monotonic Rising</span>}
            />
            <StatRow
              label="Calculation Basis"
              value={<span className="font-mono text-2xs">FLOATING_EQUITY</span>}
            />
            <StatRow
              label="Engine Status"
              value={<Badge variant="success">ACTIVE ENGINE</Badge>}
            />
          </div>
        </Panel>

        {/* Operational Invariants */}
        <Panel title="System Invariants & Safeguards">
          <div className="px-4 py-3">
            <StatRow
              label="Reset Boundary"
              value={<span className="font-mono text-2xs">UTC 00:00 Daily</span>}
            />
            <StatRow
              label="Cent Account Normalization"
              value={<span className="font-mono text-2xs">10,000 cents = $100 USD</span>}
            />
            <StatRow
              label="Staleness Gate"
              value={<span className="font-mono text-2xs">≤ 2000ms max age</span>}
            />
            <StatRow
              label="Reconciliation Guard"
              value={<Badge variant="success">AUTO-CIRCUIT BREAKER</Badge>}
            />
            <StatRow
              label="Multi-Account Isolation"
              value={<Badge variant="accent">STRICT TENANT ISOLATION</Badge>}
            />
            <StatRow
              label="Veto Authority"
              value={<span className="font-mono text-2xs text-aurexis-danger font-semibold">RISK &gt; BRAIN</span>}
            />
          </div>
        </Panel>
      </div>

      {/* Philosophy Rule Card */}
      <div className="bg-aurexis-surface border border-aurexis-border/60 rounded p-4 text-2xs font-mono text-aurexis-faint space-y-1.5">
        <div className="flex items-center gap-2 text-aurexis-accent font-semibold uppercase tracking-wider">
          <span>Cardinal Rule of Capital Preservation</span>
        </div>
        <p className="leading-relaxed">
          AUREXIS never increases position size or risks capital to achieve a daily target. Profit targets are secondary to capital preservation. If maximizing profit conflicts with preserving a locked risk rule, the risk rule wins.
        </p>
      </div>
    </div>
  );
}
