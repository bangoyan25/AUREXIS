"use client";

/**
 * SystemStatusBanner
 *
 * Displays a persistent top banner reflecting the real backend health status.
 * Never shows fake healthy state.
 * Uses SWR for polling — does not require WebSocket at this stage.
 */

import useSWR from "swr";
import type { SystemHealth } from "@/types/domain";
import { healthApi } from "@/lib/api";

const POLL_INTERVAL_MS = 30_000;

function StatusDot({ healthy }: { healthy: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full mr-1.5 ${
        healthy ? "bg-aurexis-success" : "bg-aurexis-danger"
      }`}
      aria-hidden="true"
    />
  );
}

export function SystemStatusBanner() {
  const { data, error, isLoading } = useSWR<SystemHealth>(
    "/api/v1/health",
    () => healthApi.getHealth(),
    { refreshInterval: POLL_INTERVAL_MS, revalidateOnFocus: true },
  );

  if (isLoading) {
    return (
      <div className="bg-aurexis-surface border-b border-aurexis-border px-4 py-2 text-xs text-aurexis-subtle flex items-center gap-2">
        <span className="inline-block w-2 h-2 rounded-full bg-aurexis-warning animate-pulse" />
        Connecting to AUREXIS backend…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-aurexis-surface border-b border-aurexis-danger px-4 py-2 text-xs text-aurexis-danger flex items-center gap-2">
        <StatusDot healthy={false} />
        Backend unavailable — all trading operations suspended.
      </div>
    );
  }

  const isHealthy = data.status === "healthy";
  const riskConfigured =
    data.components.risk_engine.status === "CONFIGURED";
  const brainConfigured =
    data.components.brain.status === "CONFIGURED";

  return (
    <div
      className={`border-b px-4 py-2 text-xs flex flex-wrap items-center gap-x-4 gap-y-1 ${
        isHealthy
          ? "bg-aurexis-surface border-aurexis-border text-aurexis-subtle"
          : "bg-aurexis-surface border-aurexis-warning text-aurexis-warning"
      }`}
    >
      <span className="flex items-center font-medium">
        <StatusDot healthy={isHealthy} />
        AUREXIS {data.version} · {data.environment}
      </span>

      <span className="flex items-center">
        <StatusDot healthy={data.components.database.status === "healthy"} />
        DB
      </span>

      <span className="flex items-center">
        <StatusDot healthy={data.components.redis.status === "healthy"} />
        Redis
      </span>

      <span className="flex items-center">
        <StatusDot healthy={riskConfigured} />
        Risk Engine{!riskConfigured && " (NOT CONFIGURED)"}
      </span>

      <span className="flex items-center">
        <StatusDot healthy={brainConfigured} />
        Brain{!brainConfigured && " (NOT CONFIGURED)"}
      </span>

      <span className="flex items-center">
        <StatusDot
          healthy={data.components.mt5.status !== "NO_AGENTS" && data.components.mt5.status !== "unhealthy"}
        />
        MT5{data.components.mt5.status === "NO_AGENTS" && " (no agents)"}
      </span>

      {!riskConfigured && (
        <span className="ml-auto text-aurexis-warning font-medium">
          ⚠ Trading parameters undefined — live trading is BLOCKED
        </span>
      )}
    </div>
  );
}
