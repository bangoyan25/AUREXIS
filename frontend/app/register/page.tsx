"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Panel, Badge } from "@/components/ui/primitives";

export default function RegisterPage() {
  const router = useRouter();
  const { register, error } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [serialCode, setSerialCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (password !== confirmPassword) {
      setFormError("Passwords do not match");
      return;
    }
    if (!serialCode.trim()) {
      setFormError("A valid subscription serial code is mandatory");
      return;
    }

    setIsSubmitting(true);
    try {
      await register(email, password, displayName, serialCode.trim());
      router.push("/");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Registration failed");
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
            Create Trader Identity
          </p>
          <div className="pt-1">
            <Badge variant="warning">SIMULATION ONLY</Badge>
          </div>
        </div>

        <Panel title="Register Operator">
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            {(formError || error) && (
              <div className="p-2.5 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded text-2xs text-aurexis-danger font-mono">
                {formError || error}
              </div>
            )}

            <div className="space-y-1">
              <label className="text-2xs uppercase tracking-wide text-aurexis-subtle font-mono block">
                Display Name
              </label>
              <input
                type="text"
                required
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Chief Trader"
                className="w-full bg-aurexis-surface border border-aurexis-border rounded px-3 py-2 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              />
            </div>

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
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-aurexis-surface border border-aurexis-border rounded px-3 py-2 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              />
            </div>

            <div className="space-y-1">
              <label className="text-2xs uppercase tracking-wide text-aurexis-subtle font-mono block">
                Confirm Password
              </label>
              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-aurexis-surface border border-aurexis-border rounded px-3 py-2 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              />
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="text-2xs uppercase tracking-wide text-aurexis-subtle font-mono block">
                  Serial Code
                </label>
                <span className="text-3xs text-aurexis-faint font-mono">AURX-T[1-3]-...</span>
              </div>
              <input
                type="text"
                required
                value={serialCode}
                onChange={(e) => setSerialCode(e.target.value.toUpperCase())}
                placeholder="AURX-T1-XXXX-XXXX-XXXX"
                className="w-full bg-aurexis-surface border border-aurexis-border rounded px-3 py-2 text-xs text-aurexis-text font-mono uppercase focus:outline-none focus:border-aurexis-accent tracking-wider"
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2 bg-aurexis-accent/90 hover:bg-aurexis-accent text-aurexis-bg font-semibold text-xs tracking-wider uppercase rounded transition-colors disabled:opacity-50"
            >
              {isSubmitting ? "Activating..." : "Register & Activate License"}
            </button>
          </form>

          <div className="px-4 py-3 border-t border-aurexis-border/40 text-center text-2xs text-aurexis-faint font-mono">
            Already have an active account?{" "}
            <Link href="/login" className="text-aurexis-accent hover:underline">
              Sign In
            </Link>
          </div>
        </Panel>
      </div>
    </div>
  );
}
