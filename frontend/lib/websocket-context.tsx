"use client";
/**
 * WebSocket context — wraps existing AurexisWebSocket class.
 *
 * Rules:
 * 1. Uses existing AurexisWebSocket from lib/websocket.ts — NOT a new implementation.
 * 2. Connects only when token AND selectedAccountId are non-null.
 * 3. Disconnects cleanly on logout, account change, provider unmount.
 * 4. Token never logged, never exposed to UI.
 * 5. Account switch: disconnect old → create new connection.
 */

import React, {
  createContext, useContext, useEffect, useRef, useState, useCallback,
} from "react";
import { AurexisWebSocket } from "./websocket";
import { useAuth } from "./auth-context";
import { useSelectedAccount } from "./account-context";
import type { WsEventType, WsEvent, WsConnectionState } from "@/types/domain";

interface WebSocketContextType {
  connectionState: WsConnectionState;
  subscribe: <T>(eventType: WsEventType, handler: (event: WsEvent<T>) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const { token, isAuthenticated } = useAuth();
  const { selectedAccountId } = useSelectedAccount();
  const [connectionState, setConnectionState] = useState<WsConnectionState>("DISCONNECTED");
  const wsRef = useRef<AurexisWebSocket | null>(null);
  const subscriptionsRef = useRef<Array<{ eventType: WsEventType; handler: (e: WsEvent) => void }>>([]);

  // Build connection key to detect when to reconnect
  const shouldConnect = isAuthenticated && !!token && !!selectedAccountId;

  useEffect(() => {
    // Clean up existing connection before creating new one
    if (wsRef.current) {
      wsRef.current.disconnect();
      wsRef.current = null;
      setConnectionState("DISCONNECTED");
    }

    if (!shouldConnect) {
      return;
    }

    // Token is passed to AurexisWebSocket but never logged here
    const ws = new AurexisWebSocket("/api/v1/ws", token!, selectedAccountId!);

    // Real WebSocket lifecycle callback replaces the 200ms optimistic timer
    ws.setStateCallback((newState) => {
      setConnectionState(newState);
    });

    // Re-register all existing subscriptions on the new ws instance
    for (const { eventType, handler } of subscriptionsRef.current) {
      ws.on(eventType, handler);
    }

    ws.connect();
    wsRef.current = ws;

    return () => {
      ws.disconnect();
      wsRef.current = null;
      setConnectionState("DISCONNECTED");
    };
  }, [shouldConnect, token, selectedAccountId]);

  const subscribe = useCallback(
    <T,>(eventType: WsEventType, handler: (event: WsEvent<T>) => void) => {
      const typedHandler = handler as (e: WsEvent) => void;
      // Register on current ws instance
      let unsubFromWs: (() => void) | undefined;
      if (wsRef.current) {
        unsubFromWs = wsRef.current.on(eventType, handler);
      }
      // Track in subscriptions list so future reconnects re-register
      subscriptionsRef.current.push({ eventType, handler: typedHandler });

      return () => {
        unsubFromWs?.();
        subscriptionsRef.current = subscriptionsRef.current.filter(
          (s) => s.handler !== typedHandler,
        );
      };
    },
    [],
  );

  return (
    <WebSocketContext.Provider value={{ connectionState, subscribe }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket(): WebSocketContextType {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return ctx;
}
