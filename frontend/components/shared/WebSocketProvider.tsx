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
  data: unknown;
}

interface WebSocketContextValue {
  isConnected: boolean;
  subscribe: (topic: string, callback: (data: unknown) => void) => () => void;
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
  const subscriptionsRef = useRef<Map<string, Set<(data: unknown) => void>>>(new Map());
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  function connect() {
    try {
      const ws = new WebSocket(WS_BASE_URL);

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
          callbacks?.forEach((cb) => cb(msg.data));
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

  function subscribe(topic: string, callback: (data: unknown) => void) {
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
