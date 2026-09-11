"use client";

/**
 * DashboardShell
 *
 * Main layout container for the AUREXIS trading dashboard.
 * All panels are server-state-driven — no fake data is rendered.
 * Undefined/unimplemented panels show explicit placeholder states.
 */

export function DashboardShell() {
  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <header className="bg-aurexis-surface border-b border-aurexis-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-aurexis-accent font-mono font-bold text-xl tracking-widest">
            AUREXIS
          </span>
          <span className="text-aurexis-subtle text-xs font-mono">
            XAUUSD · MT5
          </span>
        </div>

        {/* Account selector placeholder */}
        <div className="flex items-center gap-2 bg-aurexis-muted rounded px-3 py-1.5 text-xs text-aurexis-subtle">
          <span>No account connected</span>
        </div>
      </header>

      {/* Main grid */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-px bg-aurexis-border">
        {/* Left column: Account overview + Risk panel */}
        <div className="bg-aurexis-bg flex flex-col gap-px">
          <PanelPlaceholder title="Account Overview" reason="No account connected" />
          <PanelPlaceholder
            title="Risk Panel"
            reason="Risk Engine — NOT CONFIGURED"
            variant="warning"
          />
        </div>

        {/* Center column: Live positions + Trade history */}
        <div className="bg-aurexis-bg flex flex-col gap-px lg:col-span-1">
          <PanelPlaceholder title="Live Positions" reason="No open positions" />
          <PanelPlaceholder title="Trade History" reason="No closed trades" />
        </div>

        {/* Right column: System health + Brain status */}
        <div className="bg-aurexis-bg flex flex-col gap-px">
          <SystemHealthPanel />
          <PanelPlaceholder
            title="Brain / Signal Status"
            reason="Strategy parameters UNDEFINED — no signals generated"
            variant="warning"
          />
        </div>
      </div>

      {/* PNL Calendar — full width */}
      <div className="bg-aurexis-bg border-t border-aurexis-border">
        <PanelPlaceholder title="PNL Calendar" reason="No trade data" />
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PanelPlaceholder({
  title,
  reason,
  variant = "default",
}: {
  title: string;
  reason: string;
  variant?: "default" | "warning";
}) {
  return (
    <section className="p-4 flex flex-col gap-2 min-h-32">
      <h2 className="text-xs font-medium text-aurexis-subtle uppercase tracking-wider">
        {title}
      </h2>
      <div
        className={`flex-1 flex items-center justify-center text-xs font-mono rounded border ${
          variant === "warning"
            ? "border-aurexis-warning/30 text-aurexis-warning"
            : "border-aurexis-border text-aurexis-subtle"
        }`}
      >
        {reason}
      </div>
    </section>
  );
}

function SystemHealthPanel() {
  return (
    <section className="p-4 flex flex-col gap-2 min-h-32">
      <h2 className="text-xs font-medium text-aurexis-subtle uppercase tracking-wider">
        System Health
      </h2>
      <p className="text-xs text-aurexis-subtle font-mono">
        Health details shown in status banner above.
        Full health dashboard panel will be implemented in Phase 6.
      </p>
    </section>
  );
}
