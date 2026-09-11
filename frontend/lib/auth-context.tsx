"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authApi, type MeResponse, type TokenResponse } from "./api";

export interface AuthContextType {
  user: MeResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string, serialCode: string) => Promise<void>;
  logout: () => void;
  error: string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = "aurexis_token";
const REFRESH_KEY = "aurexis_refresh_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    if (token) {
      authApi.logout(token).catch(() => {});
    }
    setToken(null);
    setUser(null);
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(REFRESH_KEY);
    }
  }, [token]);

  const loadUser = useCallback(async (authToken: string) => {
    try {
      const me = await authApi.me(authToken);
      setUser(me);
      setToken(authToken);
    } catch {
      logout();
    } finally {
      setIsLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    if (typeof window === "undefined") {
      setIsLoading(false);
      return;
    }
    const savedToken = sessionStorage.getItem(TOKEN_KEY);
    if (savedToken) {
      loadUser(savedToken);
    } else {
      setIsLoading(false);
    }
  }, [loadUser]);

  const login = async (email: string, password: string) => {
    setError(null);
    setIsLoading(true);
    try {
      const resp: TokenResponse = await authApi.login({ email, password });
      setToken(resp.access_token);
      if (typeof window !== "undefined") {
        sessionStorage.setItem(TOKEN_KEY, resp.access_token);
        sessionStorage.setItem(REFRESH_KEY, resp.refresh_token);
      }
      const me = await authApi.me(resp.access_token);
      setUser(me);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Authentication failed";
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, password: string, displayName: string, serialCode: string) => {
    setError(null);
    setIsLoading(true);
    try {
      await authApi.register({
        email,
        password,
        display_name: displayName,
        serial_code: serialCode,
      });
      await login(email, password);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed";
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        register,
        logout,
        error,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
