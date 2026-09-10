"use client";
/**
 * Phase 3 observability badges — broker-agnostic.
 * Renders live market-data freshness, MT5 agent link state, and Risk Gate decision.
 */
import { Badge } from "./primitives";

type V = "default" | "success" | "danger" | "warning" | "info" | "accent" | "muted";

/** Market data freshness: FRESH / STALE / NO_DATA */
export function FreshnessBadge({ status }: { status: string }) {
  const m: Record<string, V> = {
    FRESH: "success",
    STALE: "warning",
    NO_DATA: "muted",
  };
  return <Badge variant={m[status] ?? "muted"}>{status.replace(/_/g, " ")}</Badge>;
}

/** MT5 agent link state: CONNECTED / DISCONNECTED / STALE / UNKNOWN */
export function AgentLinkBadge({ status }: { status: string }) {
  const m: Record<string, V> = {
    CONNECTED: "success",
    DISCONNECTED: "danger",
    ERROR: "danger",
    STALE: "warning",
    UNKNOWN: "muted",
    NOT_ATTACHED: "muted",
  };
  return <Badge variant={m[status] ?? "muted"}>{status.replace(/_/g, " ")}</Badge>;
}

/** Authoritative server-side Risk Gate decision: ALLOW / BLOCK */
export function RiskDecisionBadge({ decision }: { decision: string }) {
  const m: Record<string, V> = {
    ALLOW: "success",
    BLOCK: "danger",
  };
  return <Badge variant={m[decision] ?? "muted"}>{decision}</Badge>;
}

/** Deterministic reason code emitted by the Risk Gate (never fabricated client-side) */
export function ReasonCodeBadge({ code, decision }: { code: string; decision?: string }) {
  const variant: V = decision === "ALLOW" || code === "RISK_OK" ? "success" : "warning";
  return <Badge variant={variant}>{code.replace(/_/g, " ")}</Badge>;
}
