"use client";
import { Panel, Label } from "@/components/ui/primitives";
import { NewsStateBadge } from "@/components/ui/badges";
import { useNews } from "@/lib/hooks/useNews";

export function NewsPanel() {
  const news = useNews();

  if (news.status === "LOADING") {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
          <Label>News</Label>
        </div>
        <div className="px-4 py-4 text-center">
          <span className="text-2xs font-mono text-aurexis-faint animate-pulse">LOADING...</span>
        </div>
      </Panel>
    );
  }

  if (news.status === "ERROR") {
    return (
      <Panel>
        <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
          <Label>News</Label>
        </div>
        <div className="px-4 py-4 text-center">
          <p className="text-2xs font-mono text-aurexis-danger">Unable to load news state</p>
        </div>
      </Panel>
    );
  }

  const n = news.data;
  // Preserve backend state exactly: UNKNOWN ≠ CLEAR
  const newsState = (n.status as string).toUpperCase();

  return (
    <Panel>
      <div className="px-4 py-3 border-b border-aurexis-border flex items-center justify-between">
        <Label>News</Label>
        <NewsStateBadge state={newsState as Parameters<typeof NewsStateBadge>[0]["state"]} />
      </div>
      <div className="px-4 py-3">
        {newsState === "UNKNOWN"
          ? <p className="text-2xs text-aurexis-faint leading-relaxed">Provider not configured. UNKNOWN treated as PRE_EVENT — no new entries.</p>
          : newsState === "CLEAR"
            ? <p className="text-xs text-aurexis-subtle">No high-impact events in window.</p>
            : <p className="text-xs text-aurexis-warning font-medium">Trading BLOCKED — news protection active.</p>
        }
        {n.provider && (
          <p className="text-2xs text-aurexis-faint font-mono mt-1">Provider: {n.provider}</p>
        )}
      </div>
    </Panel>
  );
}

