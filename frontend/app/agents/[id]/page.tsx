"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Panel, Badge, StatRow } from "@/components/ui/primitives";
import { agentsApi, type AgentResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useAgentCommands } from "@/lib/hooks/useAgentCommands";

export default function AgentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { token, isAuthenticated } = useAuth();
  const [agent, setAgent] = useState<AgentResponse | null>(null);
  const [agentLoading, setAgentLoading] = useState(true);
  const [agentError, setAgentError] = useState<string | null>(null);
  const { commands, loading: cmdLoading, error: cmdError, sendCommand, sending, refetch } = useAgentCommands(id);

  useEffect(() => {
    if (!token || !isAuthenticated) return;
    setAgentLoading(true);
    agentsApi.get(id, token)
      .then((d) => { setAgent(d); setAgentError(null); })
      .catch((e) => { setAgentError(e instanceof Error ? e.message : "Failed to load agent"); })
      .finally(() => setAgentLoading(false));
  }, [id, token, isAuthenticated]);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Link href="/agents" className="text-2xs font-mono uppercase tracking-wider text-aurexis-accent hover:underline">
                &larr; Agents
              </Link>
              <span className="text-aurexis-faint">/</span>
              <span className="text-2xs font-mono text-aurexis-subtle">{id}</span>
            </div>
            <h1 className="text-base font-medium text-aurexis-text mt-1">{agent ? agent.label : "Agent Details"}</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => sendCommand("PING").catch(() => {})} disabled={sending}
              className="px-3 py-1.5 bg-aurexis-surface hover:bg-aurexis-muted border border-aurexis-border text-xs font-mono uppercase tracking-wider text-aurexis-text rounded transition-colors disabled:opacity-50">
              {sending ? "Sending..." : "Dispatch PING"}
            </button>
            <button onClick={() => sendCommand("GET_STATUS").catch(() => {})} disabled={sending}
              className="px-3 py-1.5 bg-aurexis-surface hover:bg-aurexis-muted border border-aurexis-border text-xs font-mono uppercase tracking-wider text-aurexis-text rounded transition-colors disabled:opacity-50">
              {sending ? "Sending..." : "GET_STATUS"}
            </button>
          </div>
        </div>
        {agentLoading ? (
          <div className="px-4 py-8 text-center text-2xs font-mono text-aurexis-faint animate-pulse">LOADING AGENT...</div>
        ) : agentError ? (
          <div className="p-4 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded text-xs text-aurexis-danger font-mono">{agentError}</div>
        ) : agent ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Panel title="Agent Metadata">
              <div className="p-4 space-y-1">
                <StatRow label="Agent ID" value={<span className="font-mono text-2xs text-aurexis-subtle">{agent.id}</span>} />
                <StatRow label="Account ID" value={<span className="font-mono text-2xs text-aurexis-subtle">{agent.account_id}</span>} />
                <StatRow label="Status" value={<Badge variant={agent.last_known_status === "CONNECTED" ? "success" : "danger"}>{agent.last_known_status}</Badge>} />
                <StatRow label="EA Version" value={<span className="font-mono">{agent.ea_version ?? "N/A"}</span>} />
                <StatRow label="MT5 Version" value={<span className="font-mono">{agent.mt5_version ?? "N/A"}</span>} />
                <StatRow label="Last Seen" value={agent.last_seen_at ? new Date(agent.last_seen_at).toLocaleString() : "Never"} />
              </div>
            </Panel>
            <Panel title="Security Notice">
              <div className="p-4 space-y-2 text-2xs text-aurexis-faint leading-relaxed font-mono">
                <p>&bull; Agent secret write-only on creation; never exposed via API.</p>
                <p>&bull; Dispatch requires authenticated owner Bearer JWT.</p>
                <p>&bull; Persistent WSS transport via /api/v1/agents/&#123;id&#125;/ws.</p>
              </div>
            </Panel>
          </div>
        ) : null}

        <Panel title="Command History" action={<button onClick={() => void refetch()} className="text-2xs font-mono uppercase text-aurexis-subtle hover:text-aurexis-text">Refresh</button>}>
          {cmdLoading ? (
            <div className="px-4 py-8 text-center text-2xs font-mono text-aurexis-faint animate-pulse">LOADING COMMANDS...</div>
          ) : cmdError ? (
            <div className="px-4 py-8 text-center text-2xs font-mono text-aurexis-danger">{cmdError}</div>
          ) : commands.length === 0 ? (
            <div className="px-4 py-8 text-center text-2xs text-aurexis-faint font-mono">No commands recorded. Use buttons above to dispatch.</div>
          ) : (
            <div className="divide-y divide-aurexis-border/40">
              {commands.map((cmd) => (
                <div key={cmd.id} className="p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-medium text-aurexis-text">{cmd.command_type}</span>
                      <Badge variant={cmd.status === "COMPLETED" ? "success" : cmd.status === "FAILED" ? "danger" : "warning"}>{cmd.status}</Badge>
                    </div>
                    <span className="text-2xs font-mono text-aurexis-faint">{new Date(cmd.created_at).toLocaleTimeString()}</span>
                  </div>
                  <div className="text-2xs font-mono text-aurexis-subtle flex gap-4">
                    <span>ID: {cmd.id}</span>
                    {cmd.completed_at && <span>Done: {new Date(cmd.completed_at).toLocaleTimeString()}</span>}
                  </div>
                  {cmd.result && (
                    <pre className="p-2 bg-aurexis-elevated border border-aurexis-border rounded font-mono text-2xs text-aurexis-text overflow-x-auto">{JSON.stringify(cmd.result, null, 2)}</pre>
                  )}
                  {cmd.error_message && (
                    <div className="p-2 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded font-mono text-2xs text-aurexis-danger">{cmd.error_message}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}

