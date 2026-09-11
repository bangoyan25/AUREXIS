"use client";
/**
 * AUREXIS app shell — sidebar + header + content layout.
 * Wires real health data and account selection into GlobalHeader.
 */
import { Sidebar } from "./Sidebar";
import { GlobalHeader } from "./GlobalHeader";
import { useAuth } from "@/lib/auth-context";
import { useSelectedAccount } from "@/lib/account-context";
import { useHealth } from "@/lib/hooks/useHealth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

function deriveSystemStatus(health: ReturnType<typeof useHealth>): "ONLINE" | "DEGRADED" | "WARNING" | "OFFLINE" | "UNKNOWN" {
  if (health.status === "LOADING") return "UNKNOWN";
  if (health.status === "ERROR") return "OFFLINE";
  const s = health.data?.status;
  if (s === "healthy") return "ONLINE";
  if (s === "degraded") return "DEGRADED";
  if (s === "unhealthy") return "OFFLINE";
  return "UNKNOWN";
}

function deriveBrainStatus(health: ReturnType<typeof useHealth>): "OK" | "NOT_CONFIGURED" | "ERROR" | "UNKNOWN" {
  if (health.status !== "OK") return "UNKNOWN";
  const b = health.data?.components?.brain?.status;
  if (b === "healthy" || b === "CONFIGURED") return "OK";
  if (b === "NOT_CONFIGURED") return "NOT_CONFIGURED";
  if (b === "unhealthy") return "ERROR";
  return "UNKNOWN";
}

function deriveMt5Status(health: ReturnType<typeof useHealth>): "CONNECTED" | "DISCONNECTED" | "NO_AGENTS" | "UNKNOWN" {
  if (health.status !== "OK") return "UNKNOWN";
  const m = health.data?.components?.mt5?.status;
  if (m === "healthy") return "CONNECTED";
  if (m === "NO_AGENTS") return "NO_AGENTS";
  if (m === "unhealthy") return "DISCONNECTED";
  return "UNKNOWN";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user, logout } = useAuth();
  const { selectedAccount } = useSelectedAccount();
  const health = useHealth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-aurexis-bg flex items-center justify-center">
        <span className="text-2xs font-mono uppercase tracking-widest text-aurexis-faint animate-pulse">
          INITIALIZING...
        </span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  const accountLabel = selectedAccount?.label ?? user?.display_name ?? "Trader";

  return (
    <>
      <Sidebar />
      <GlobalHeader
        systemStatus={deriveSystemStatus(health)}
        brainStatus={deriveBrainStatus(health)}
        mt5Status={deriveMt5Status(health)}
        account={accountLabel}
        onLogout={logout}
      />
      <main
        className="ml-sidebar pt-12 min-h-screen bg-aurexis-bg"
        id="main-content"
      >
        <div className="p-6">
          {children}
        </div>
      </main>
    </>
  );
}


