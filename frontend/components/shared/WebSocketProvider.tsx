"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { WS_BASE_URL } from "@/lib/constants";

interface WebSocketMessage {
  topic: string;
  /** Backend publishers always set this — e.g. `deployment_status`,
   *  `deployment_deleted`, `telemetry`, `policy_activated`. */
  event?: string;
  data: unknown;
}

/** Subscribers receive the event name too; several topics multiplex more than
 *  one event kind and previously there was no way to tell them apart. */
type Subscriber = (data: unknown, event?: string) => void;

interface WebSocketContextValue {
  isConnected: boolean;
  subscribe: (topic: string, callback: Subscriber) => () => void;
  send: (topic: string, data: unknown) => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export function useWebSocket() {
  const ctx = useContext(WebSocketContext);
  if (!ctx) throw new Error("useWebSocket must be used within WebSocketProvider");
  return ctx;
}

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const subscriptionsRef = useRef<Map<string, Set<Subscriber>>>(new Map());
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  function connect() {
    try {
      // The backend's WS hub authenticates via `?token=` (browsers cannot set
      // headers on a handshake), so forward the stored project API key.
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("llcp_api_key")
          : null;
      const url = token ? `${WS_BASE_URL}?token=${encodeURIComponent(token)}` : WS_BASE_URL;
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setIsConnected(true);
        // Re-subscribe to all topics on reconnect
        for (const topic of subscriptionsRef.current.keys()) {
          ws.send(JSON.stringify({ action: "subscribe", topic }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);
          const callbacks = subscriptionsRef.current.get(msg.topic);
          callbacks?.forEach((cb) => cb(msg.data, msg.event));
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };

      wsRef.current = ws;
    } catch {
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    }
  }

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeoutRef.current);
      wsRef.current?.close();
    };
  }, []);

  function subscribe(topic: string, callback: Subscriber) {
    if (!subscriptionsRef.current.has(topic)) {
      subscriptionsRef.current.set(topic, new Set());
      // Send subscribe message if connected
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ action: "subscribe", topic }));
      }
    }
    subscriptionsRef.current.get(topic)!.add(callback);

    return () => {
      subscriptionsRef.current.get(topic)?.delete(callback);
      if (subscriptionsRef.current.get(topic)?.size === 0) {
        subscriptionsRef.current.delete(topic);
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ action: "unsubscribe", topic }));
        }
      }
    };
  }

  function send(topic: string, data: unknown) {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ topic, data }));
    }
  }

  return (
    <WebSocketContext.Provider value={{ isConnected, subscribe, send }}>
      {children}
    </WebSocketContext.Provider>
  );
}
