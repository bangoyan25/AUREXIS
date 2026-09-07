/**
 * AUREXIS WebSocket client.
 *
 * Server-controlled realtime events.
 * The frontend is a display consumer — it does not generate trading state.
 * All trading state originates from the backend.
 */

import type { WsConnectionState, WsEvent, WsEventType } from "@/types/domain";

const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

type EventHandler<T = unknown> = (event: WsEvent<T>) => void;
type StateChangeCallback = (state: WsConnectionState) => void;

export class AurexisWebSocket {
  private ws: WebSocket | null = null;
  private handlers = new Map<WsEventType, Set<EventHandler>>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 2000;
  private maxReconnectDelay = 30000;
  private stopped = false;
  private stateCallback: StateChangeCallback | null = null;

  constructor(
    private readonly path: string = "/api/v1/ws",
    private readonly token?: string,
    private readonly accountId?: string,
  ) {}

  /**
   * Register a callback for connection state changes.
   * Called with: "CONNECTING" before connect, "CONNECTED" on open,
   * "DISCONNECTED" on close, "ERROR" on error.
   * Do not create a second WS implementation — extend only.
   */
  setStateCallback(cb: StateChangeCallback): void {
    this.stateCallback = cb;
  }

  connect(): void {
    if (this.stopped) return;
    const params = new URLSearchParams();
    if (this.token) params.set("token", this.token);
    if (this.accountId) params.set("account_id", this.accountId);
    const qs = params.toString();
    const url = `${WS_BASE}${this.path}${qs ? `?${qs}` : ""}`;
    this.ws = new WebSocket(url);
    this.stateCallback?.("CONNECTING");

    this.ws.onopen = () => {
      console.info("[AUREXIS WS] connected");
      this.reconnectDelay = 2000; // reset on successful connect
      this.stateCallback?.("CONNECTED");
    };

    this.ws.onmessage = (ev: MessageEvent) => {
      try {
        const event = JSON.parse(ev.data as string) as WsEvent;
        const handlers = this.handlers.get(event.event);
        handlers?.forEach((h) => h(event));
      } catch {
        console.warn("[AUREXIS WS] failed to parse event", ev.data);
      }
    };

    this.ws.onclose = () => {
      console.info("[AUREXIS WS] disconnected — will reconnect");
      this.stateCallback?.("DISCONNECTED");
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.error("[AUREXIS WS] error", err);
      this.stateCallback?.("ERROR");
    };
  }

  on<T>(eventType: WsEventType, handler: EventHandler<T>): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler as EventHandler);
    // Return unsubscribe function
    return () => {
      this.handlers.get(eventType)?.delete(handler as EventHandler);
    };
  }

  disconnect(): void {
    this.stopped = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  private scheduleReconnect(): void {
    if (this.stopped) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectDelay = Math.min(
        this.reconnectDelay * 1.5,
        this.maxReconnectDelay,
      );
      this.connect();
    }, this.reconnectDelay);
  }
}
