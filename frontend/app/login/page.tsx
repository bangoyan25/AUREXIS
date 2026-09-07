"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Panel, Badge } from "@/components/ui/primitives";

export default function LoginPage() {
  const router = useRouter();
  const { login, error } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-aurexis-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-4">
        <div className="text-center space-y-1">
          <h1 className="text-xl font-display font-semibold tracking-[0.2em] text-aurexis-accent">
            AUREXIS
          </h1>
          <p className="text-2xs font-mono tracking-widest text-aurexis-faint uppercase">
            Trading Intelligence Platform
          </p>
          <div className="pt-1">
            <Badge variant="warning">SIMULATION ONLY</Badge>
          </div>
        </div>

        <Panel title="Trader Authentication">
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            {(formError || error) && (
              <div className="p-2.5 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded text-2xs text-aurexis-danger font-mono">
                {formError || error}
              </div>
            )}

            <div className="space-y-1">
              <label className="text-2xs uppercase tracking-wide text-aurexis-subtle font-mono block">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="trader@aurexis.local"
                className="w-full bg-aurexis-surface border border-aurexis-border rounded px-3 py-2 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              />
            </div>

            <div className="space-y-1">
              <label className="text-2xs uppercase tracking-wide text-aurexis-subtle font-mono block">
                Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-aurexis-surface border border-aurexis-border rounded px-3 py-2 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2 bg-aurexis-accent/90 hover:bg-aurexis-accent text-aurexis-bg font-semibold text-xs tracking-wider uppercase rounded transition-colors disabled:opacity-50"
            >
              {isSubmitting ? "Authenticating..." : "Sign In"}
            </button>
          </form>
        </Panel>

        <div className="text-center text-2xs text-aurexis-faint font-mono">
          Live Trading is strictly disabled on this terminal.
        </div>
      </div>
    </div>
  );
}
