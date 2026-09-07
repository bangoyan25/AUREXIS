"use client";
/**
 * useAccounts — manages trading accounts via GET /api/v1/accounts.
 * Supports CRUD operations.
 */
import { useState, useEffect, useCallback } from "react";
import { accountsApi, type AccountResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export function useAccounts() {
  const { token, isAuthenticated } = useAuth();
  const [data, setData] = useState<AccountResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAccounts = useCallback(async () => {
    if (!token || !isAuthenticated) {
      setData([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await accountsApi.list(token);
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load accounts";
      setError(msg);
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [token, isAuthenticated]);

  useEffect(() => {
    void fetchAccounts();
  }, [fetchAccounts]);

  const createAccount = useCallback(
    async (body: object) => {
      if (!token) throw new Error("Unauthenticated");
      const created = await accountsApi.create(body, token);
      await fetchAccounts();
      return created;
    },
    [token, fetchAccounts],
  );

  const updateAccount = useCallback(
    async (id: string, body: object) => {
      if (!token) throw new Error("Unauthenticated");
      const updated = await accountsApi.patch(id, body, token);
      await fetchAccounts();
      return updated;
    },
    [token, fetchAccounts],
  );

  const deleteAccount = useCallback(
    async (id: string) => {
      if (!token) throw new Error("Unauthenticated");
      await accountsApi.delete(id, token);
      await fetchAccounts();
    },
    [token, fetchAccounts],
  );

  return {
    data,
    accounts: data,
    loading,
    error,
    refetch: fetchAccounts,
    createAccount,
    updateAccount,
    deleteAccount,
  };
}
