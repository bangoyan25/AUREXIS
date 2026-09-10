"use client";

import { Panel } from "@/components/ui/primitives";
import type { RegisterAgentResponse } from "@/lib/api";

interface Props {
  data: RegisterAgentResponse;
  onClose: () => void;
}

export function SecretDisplayModal({ data, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-lg">
        <Panel title="Agent Registered — SAVE YOUR SECRET">
          <div className="p-4 space-y-4">
            <div className="p-3 bg-aurexis-danger/10 border border-aurexis-danger/40 rounded">
              <p className="text-xs font-mono font-medium text-aurexis-danger leading-relaxed">
                The secret below is shown ONCE. It is never stored in plaintext and cannot be recovered. Copy it immediately.
              </p>
            </div>

            <div>
              <p className="text-2xs font-mono text-aurexis-subtle mb-1">Agent ID</p>
              <div className="p-2 bg-aurexis-elevated border border-aurexis-border rounded font-mono text-xs text-aurexis-text break-all select-all">
                {data.id}
              </div>
            </div>

            <div>
              <p className="text-2xs font-mono text-aurexis-subtle mb-1">Agent Secret (copy now)</p>
              <div className="p-2 bg-aurexis-elevated border border-aurexis-accent/50 rounded font-mono text-xs text-aurexis-accent break-all select-all">
                {data.agent_secret}
              </div>
            </div>

            <div className="p-3 bg-aurexis-surface border border-aurexis-border rounded space-y-1">
              <p className="text-2xs font-mono text-aurexis-subtle font-medium">MT5 EA Parameters</p>
              <p className="text-2xs font-mono text-aurexis-faint">In MT5 AurexisAgent Inputs:</p>
              <p className="text-2xs font-mono text-aurexis-faint">InpAgentId = {data.id}</p>
              <p className="text-2xs font-mono text-aurexis-faint">InpAgentSecret = [paste secret above]</p>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="w-full py-2 bg-aurexis-accent hover:bg-aurexis-accent/80 text-black text-xs font-mono uppercase tracking-wider rounded transition-colors"
            >
              I have saved the credentials — Done
            </button>
          </div>
        </Panel>
      </div>
    </div>
  );
}
