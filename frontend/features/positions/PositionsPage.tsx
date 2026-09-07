"use client";
/** Positions page — real API with WebSocket real-time invalidation. */
import { useEffect } from "react";
import { Panel, EmptyState } from "@/components/ui/primitives";
import { usePositions } from "@/lib/hooks/usePositions";
import { useWebSocket } from "@/lib/websocket-context";

export function PositionsPage() {
  const { status, data, error, refetch } = usePositions();
  const { subscribe } = useWebSocket();

  // Real-time: refetch positions when POSITION_UPDATED arrives
  useEffect(() => {
    const unsub = subscribe("POSITION_UPDATED", () => {
      void refetch();
    });
    return unsub;
  }, [subscribe, refetch]);

  const positions = status === "OK" ? data.positions : [];
  const backendNote = status === "OK" ? data.note : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">Positions</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">Open positions from MT5.</p>
      </div>

      {status === "LOADING" && (
        <div className="px-4 py-8 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
        </div>
      )}

      {status === "ERROR" && (
        <div className="bg-aurexis-danger/5 border border-aurexis-danger/20 rounded px-4 py-3">
          <p className="text-xs text-aurexis-danger font-medium">CONNECTION ERROR — {error}</p>
        </div>
      )}

      {backendNote && status === "OK" && (
        <div className="bg-aurexis-surface border border-aurexis-border/50 rounded px-4 py-2">
          <p className="text-2xs text-aurexis-faint">{backendNote}</p>
        </div>
      )}

      <Panel title="Open Positions">
        {status !== "OK" ? null : positions.length === 0 ? (
          <EmptyState title="No open positions" description="No active trades. All position state is authoritative from MT5." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-aurexis-border">
                  {["Symbol", "Dir", "Volume", "Current", "Floating PNL"].map((h) => (
                    <th key={h} className="px-4 py-2 text-left text-2xs uppercase tracking-wide text-aurexis-subtle font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(positions as Record<string, unknown>[]).map((pos, i) => (
                  <tr key={String(pos.id ?? i)} className="border-b border-aurexis-border/40 hover:bg-aurexis-muted/30">
                    <td className="px-4 py-2 font-mono">{String(pos.symbol ?? "—")}</td>
                    <td className="px-4 py-2 font-mono">{String(pos.direction ?? "—")}</td>
                    <td className="px-4 py-2 font-mono">{String(pos.volume_lots ?? "—")}</td>
                    <td className="px-4 py-2 font-mono">{String(pos.current_price ?? "—")}</td>
                    <td className="px-4 py-2 font-mono">{String(pos.floating_pnl_usd ?? "0.00")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

