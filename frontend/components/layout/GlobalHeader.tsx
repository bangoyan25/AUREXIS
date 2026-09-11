"use client";
/**
 * AUREXIS global header.
 */
import { clsx } from "clsx";
import { StatusDot, Badge } from "@/components/ui/primitives";

interface HeaderProps {
  systemStatus?: "ONLINE" | "DEGRADED" | "WARNING" | "OFFLINE" | "UNKNOWN";
  brainStatus?:  "OK" | "NOT_CONFIGURED" | "ERROR" | "UNKNOWN";
  mt5Status?:    "CONNECTED" | "DISCONNECTED" | "NO_AGENTS" | "UNKNOWN";
  account?:      string;
  price?:        string;
  onLogout?:     () => void;
}

function getDotColor(status: string): "success" | "danger" | "warning" | "muted" {
  if (status === "ONLINE" || status === "OK" || status === "CONNECTED") return "success";
  if (status === "DEGRADED" || status === "WARNING" || status === "NOT_CONFIGURED") return "warning";
  if (status === "OFFLINE" || status === "ERROR" || status === "DISCONNECTED") return "danger";
  return "muted";
}

export function GlobalHeader({
  systemStatus = "UNKNOWN",
  brainStatus  = "UNKNOWN",
  mt5Status    = "UNKNOWN",
  account      = "No account",
  price,
  onLogout,
}: HeaderProps) {
  return (
    <header
      className="fixed top-0 left-sidebar right-0 z-30 h-12 bg-aurexis-surface border-b border-aurexis-border flex items-center px-5 gap-6"
      aria-label="Global header"
    >
      {/* Platform Status Badge */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <Badge variant={process.env.NEXT_PUBLIC_TRADING_MODE === "live" ? "danger" : "accent"}>
          {process.env.NEXT_PUBLIC_TRADING_MODE === "live" ? "LIVE EXECUTION" : "AUREXIS PLATFORM"}
        </Badge>
      </div>

      <div className="w-px h-5 bg-aurexis-border flex-shrink-0" aria-hidden="true" />

      {/* System status */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <span className="flex items-center gap-1.5 text-2xs text-aurexis-subtle">
          <StatusDot color={getDotColor(systemStatus)} pulse={systemStatus === "DEGRADED"} />
          <span className="font-mono uppercase tracking-wide">{systemStatus}</span>
        </span>
      </div>

      <div className="w-px h-5 bg-aurexis-border flex-shrink-0" aria-hidden="true" />

      {/* Brain */}
      <div className="flex items-center gap-1.5 text-2xs text-aurexis-subtle flex-shrink-0">
        <StatusDot color={getDotColor(brainStatus)} />
        <span className="font-mono">BRAIN</span>
        {brainStatus === "NOT_CONFIGURED" && (
          <Badge variant="warning">NOT CONFIGURED</Badge>
        )}
      </div>

      {/* MT5 */}
      <div className="flex items-center gap-1.5 text-2xs text-aurexis-subtle flex-shrink-0">
        <StatusDot color={mt5Status === "CONNECTED" ? "success" : "danger"} />
        <span className="font-mono">MT5</span>
      </div>

      {/* Spacer */}
      <div className="flex-1" aria-hidden="true" />

      {/* Price */}
      {price ? (
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-2xs text-aurexis-faint font-mono">XAUUSD</span>
          <span className="font-financial text-sm text-aurexis-text tabular-nums">{price}</span>
        </div>
      ) : (
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-2xs text-aurexis-faint font-mono">XAUUSD</span>
          <span className="text-2xs text-aurexis-faint font-mono">—</span>
        </div>
      )}

      <div className="w-px h-5 bg-aurexis-border flex-shrink-0" aria-hidden="true" />

      {/* Account */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-2xs text-aurexis-faint font-mono uppercase tracking-wide">OPERATOR</span>
          <span className="text-xs text-aurexis-subtle font-mono">{account}</span>
        </div>
        {onLogout && (
          <button
            onClick={onLogout}
            className="text-2xs font-mono text-aurexis-faint hover:text-aurexis-danger transition-colors uppercase tracking-wider px-1.5 py-0.5 border border-aurexis-border hover:border-aurexis-danger/50 rounded"
            aria-label="Logout"
          >
            EXIT
          </button>
        )}
      </div>
    </header>
  );
}
