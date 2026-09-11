"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { authApi } from "@/lib/api";
import { Panel, Badge } from "@/components/ui/primitives";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tokenParam = searchParams.get("token") || "";

  const [token, setToken] = useState(tokenParam);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    if (!token.trim()) {
      setError("Reset token is required");
      return;
    }

    setIsSubmitting(true);
    try {
      await authApi.resetPassword({ token: token.trim(), new_password: newPassword });
      setSuccess(true);
      setTimeout(() => {
        router.push("/login");
      }, 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reset password");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Panel title="Set New Password">
      {success ? (
        <div className="p-4 space-y-3 text-center">
          <div className="p-3 bg-aurexis-success/10 border border-aurexis-success/30 rounded text-xs text-aurexis-success font-mono">
            Password updated successfully. Redirecting to sign in...
          </div>
          <Link href="/login" className="text-2xs text-aurexis-accent font-mono hover:underline block">
            Click here if not redirected
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="p-2.5 bg-aurexis-danger/10 border border-aurexis-danger/30 rounded text-2xs text-aurexis-danger font-mono">
              {error}
            </div>
          )}

          {!tokenParam && (
            <div className="space-y-1">
              <label className="text-2xs uppercase tracking-wide text-aurexis-subtle font-mono block">
                Reset Token
              </label>
              <input
                type="text"
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste token from link"
                className="w-full bg-aurexis-surface border border-aurexis-border rounded px-3 py-2 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
              />
            </div>
          )}

          <div className="space-y-1">
            <label className="text-2xs uppercase tracking-wide text-aurexis-subtle font-mono block">
              New Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full bg-aurexis-surface border border-aurexis-border rounded px-3 py-2 text-xs text-aurexis-text font-mono focus:outline-none focus:border-aurexis-accent"
            />
          </div>

          <div className="space-y-1">
            <label className="text-2xs uppercase tracking-wide text-aurexis-subtle font-mono block">
              Confirm New Password
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

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2 bg-aurexis-accent/90 hover:bg-aurexis-accent text-aurexis-bg font-semibold text-xs tracking-wider uppercase rounded transition-colors disabled:opacity-50"
          >
            {isSubmitting ? "Resetting..." : "Update Password"}
          </button>
        </form>
      )}

      <div className="px-4 py-3 border-t border-aurexis-border/40 text-center text-2xs text-aurexis-faint font-mono">
        <Link href="/login" className="text-aurexis-accent hover:underline">
          Back to Login
        </Link>
      </div>
    </Panel>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen bg-aurexis-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-4">
        <div className="text-center space-y-1">
          <h1 className="text-xl font-display font-semibold tracking-[0.2em] text-aurexis-accent">
            AUREXIS
          </h1>
          <p className="text-2xs font-mono tracking-widest text-aurexis-faint uppercase">
            Create New Password
          </p>
          <div className="pt-1">
            <Badge variant="warning">PASSWORD RESET</Badge>
          </div>
        </div>

        <Suspense fallback={<div className="text-center text-xs font-mono text-aurexis-faint">Loading...</div>}>
          <ResetPasswordForm />
        </Suspense>
      </div>
    </div>
  );
}
