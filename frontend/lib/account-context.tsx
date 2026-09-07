"use client";
/**
 * Account context — single consistent source of truth for account selection.
 *
 * Rules:
 * 1. After login, loads accounts via useAccounts().
 * 2. If accounts present: selectedAccountId = accounts[0].id.
 * 3. Supports account switching.
 * 4. If no accounts: selectedAccountId = null. Never fabricate fake accounts.
 * 5. Clears on logout.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useAccounts } from "./hooks/useAccounts";
import { useAuth } from "./auth-context";
import type { AccountResponse } from "./api";

export interface AccountContextType {
  accounts: AccountResponse[];
  selectedAccountId: string | null;
  selectedAccount: AccountResponse | null;
  selectAccount: (id: string) => void;
  loading: boolean;
  error: string | null;
  refetchAccounts: () => Promise<void>;
}

const AccountContext = createContext<AccountContextType | undefined>(undefined);

export function AccountProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { accounts, loading, error, refetch } = useAccounts();
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);

  // Auto-select first account or clear when accounts change
  useEffect(() => {
    if (!isAuthenticated) {
      setSelectedAccountId(null);
      return;
    }
    if (accounts.length > 0) {
      // If currently selected ID is still in accounts, keep it; otherwise default to first
      setSelectedAccountId((prev) => {
        if (prev && accounts.some((a) => a.id === prev)) {
          return prev;
        }
        return accounts[0]?.id ?? null;
      });
    } else {
      setSelectedAccountId(null);
    }
  }, [accounts, isAuthenticated]);

  const selectAccount = useCallback((id: string) => {
    setSelectedAccountId(id);
  }, []);

  const selectedAccount =
    accounts.find((a) => a.id === selectedAccountId) ?? null;

  return (
    <AccountContext.Provider
      value={{
        accounts,
        selectedAccountId,
        selectedAccount,
        selectAccount,
        loading,
        error,
        refetchAccounts: refetch,
      }}
    >
      {children}
    </AccountContext.Provider>
  );
}

export function useSelectedAccount(): AccountContextType {
  const ctx = useContext(AccountContext);
  if (!ctx) {
    throw new Error("useSelectedAccount must be used within an AccountProvider");
  }
  return ctx;
}
