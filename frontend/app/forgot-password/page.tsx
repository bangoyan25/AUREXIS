"use client";

import { useState } from "react";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { Panel, Badge } from "@/components/ui/primitives";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setIsSubmitting(true);
    try {
      const res = await authApi.forgotPassword({ email });
      setMessage(res.message);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Request failed");
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
            Operator Account Recovery
          </p>
          <div className="pt-1">
            <Badge variant="warning">PASSWORD RESET</Badge>
          </div>
        </div>

        <Panel title="Reset Password">
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            {error && (
              <div className="p-2.5 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded text-2xs text-aurexis-danger font-mono">
                {error}
              </div>
            )}

            {message && (
              <div className="p-2.5 bg-aurexis-success/10 border border-aurexis-success/30 rounded text-2xs text-aurexis-success font-mono">
                {message}
              </div>
            )}

            <div className="space-y-1">
              <label className="text-2xs uppercase tracking-wide text-aurexis-subtle font-mono block">
                Account Email
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

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2 bg-aurexis-accent/90 hover:bg-aurexis-accent text-aurexis-bg font-semibold text-xs tracking-wider uppercase rounded transition-colors disabled:opacity-50"
            >
              {isSubmitting ? "Sending..." : "Send Reset Link"}
            </button>
          </form>

          <div className="px-4 py-3 border-t border-aurexis-border/40 text-center text-2xs text-aurexis-faint font-mono">
            Remembered your credentials?{" "}
            <Link href="/login" className="text-aurexis-accent hover:underline">
              Back to Login
            </Link>
          </div>
        </Panel>
      </div>
    </div>
  );
}
