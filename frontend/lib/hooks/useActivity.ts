"use client";
/**
 * useActivity — GET /api/v1/activity?limit={limit}. Auth required.
 */
import { useState, useEffect, useCallback } from "react";
import { activityApi, type AuditEventResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export function useActivity(limit = 50) {
  const { token, isAuthenticated } = useAuth();
  const [data, setData] = useState<AuditEventResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchActivity = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setData([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await activityApi.list(token, limit);
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load activity";
      setError(msg);
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [token, isAuthenticated, limit]);

  useEffect(() => { void fetchActivity(); }, [fetchActivity]);

  return { data, events: data, loading, error, refetch: fetchActivity };
}
