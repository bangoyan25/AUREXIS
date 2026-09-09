"use client";
/** MT5 Agents page — real API. */
import Link from "next/link";
import { Panel, EmptyState, Badge } from "@/components/ui/primitives";
import { useAgents } from "@/lib/hooks/useAgents";

function getStatusVariant(status: string) {
  if (status === "CONNECTED") return "success";
  if (status === "DISCONNECTED" || status === "ERROR") return "danger";
  return "muted";
}

export function AgentsPage() {
  const { agents, loading, error } = useAgents();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">MT5 Agents</h1>
        <p className="text-2xs text-aurexis-faint mt-0.5">MT5 execution agents. Architecture supports 5+ accounts.</p>
      </div>
      <Panel title="Registered Agents">
        {loading ? (
          <div className="px-4 py-8 text-center">
            <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
          </div>
        ) : error ? (
          <div className="px-4 py-8 text-center">
            <p className="text-2xs font-mono text-aurexis-danger">{error}</p>
          </div>
        ) : agents.length === 0 ? (
          <EmptyState
            title="No MT5 agents"
            description="No MT5 agents registered. Deploy MT5 EA on Windows VPS and configure connection."
          />
        ) : (
          <div className="divide-y divide-aurexis-border/40">
            {agents.map((agent) => (
              <div key={agent.id} className="flex items-center justify-between px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-aurexis-text">{agent.label}</p>
                  <p className="text-2xs text-aurexis-faint font-mono mt-0.5">
                    {agent.account_id} · EA v{agent.ea_version ?? "unknown"}
                    {agent.last_seen_at && ` · seen ${new Date(agent.last_seen_at).toLocaleTimeString()}`}
                  </p>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <Badge variant={getStatusVariant(agent.last_known_status)}>
                    {agent.last_known_status}
                  </Badge>
                  <Link
                    href={`/agents/${agent.id}`}
                    className="text-2xs font-mono uppercase tracking-wider text-aurexis-accent hover:underline"
                  >
                    Details →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}


