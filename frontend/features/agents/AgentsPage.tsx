"use client";
/** MT5 Agents page — real API with Agent Registration and Secret Display. */
import { useState } from "react";
import Link from "next/link";
import { Panel, EmptyState, Badge } from "@/components/ui/primitives";
import { useAgents } from "@/lib/hooks/useAgents";
import { useAccounts } from "@/lib/hooks/useAccounts";
import type { RegisterAgentResponse } from "@/lib/api";
import { RegisterAgentForm } from "./RegisterAgentForm";
import { SecretDisplayModal } from "./SecretDisplayModal";

function getStatusVariant(status: string) {
  if (status === "CONNECTED") return "success";
  if (status === "DISCONNECTED" || status === "ERROR") return "danger";
  return "muted";
}

export function AgentsPage() {
  const { agents, loading, error, registerAgent, refetch } = useAgents();
  const { accounts } = useAccounts();
  const [showRegister, setShowRegister] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [newAgentData, setNewAgentData] = useState<RegisterAgentResponse | null>(null);

  const handleRegister = async (body: { account_id: string; label: string; notes?: string | null }) => {
    setRegistering(true);
    setRegisterError(null);
    try {
      const res = await registerAgent(body);
      setShowRegister(false);
      setNewAgentData(res);
      void refetch();
    } catch (err: unknown) {
      setRegisterError(err instanceof Error ? err.message : "Failed to register agent");
    } finally {
      setRegistering(false);
    }
  };

  return (
    <div className="space-y-4">
      {newAgentData && (
        <SecretDisplayModal
          data={newAgentData}
          onClose={() => setNewAgentData(null)}
        />
      )}

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xs font-medium uppercase tracking-widest text-aurexis-subtle">MT5 Agents</h1>
          <p className="text-2xs text-aurexis-faint mt-0.5">MT5 execution agents. Architecture supports 5+ accounts.</p>
        </div>
        <button
          onClick={() => { setShowRegister((v) => !v); setRegisterError(null); }}
          className="px-3 py-1.5 bg-aurexis-accent hover:bg-aurexis-accent/80 text-black text-2xs font-mono uppercase tracking-wider rounded transition-colors"
        >
          {showRegister ? "Cancel" : "+ Register Agent"}
        </button>
      </div>

      {showRegister && (
        <RegisterAgentForm
          accounts={accounts}
          onRegistered={handleRegister}
          onCancel={() => setShowRegister(false)}
          registering={registering}
          error={registerError}
        />
      )}

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
            description="No MT5 agents registered. Click '+ Register Agent' above to generate credentials, then configure your MT5 EA on Windows VPS."
          />
        ) : (
          <div className="divide-y divide-aurexis-border/40">
            {agents.map((agent) => (
              <div key={agent.id} className="flex items-center justify-between px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-aurexis-text">{agent.label}</p>
                  <p className="text-2xs text-aurexis-faint font-mono mt-0.5">
                    {agent.id} · EA v{agent.ea_version ?? "unknown"}
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


