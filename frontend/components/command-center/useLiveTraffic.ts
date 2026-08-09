"use client";

import { useEffect, useRef } from "react";
import { useWebSocket } from "@/components/shared/WebSocketProvider";

export interface LiveTrafficRefs {
  // Requests per second the particle system should emit.
  rateRef: React.MutableRefObject<number>;
  // True when no real gateway traffic has arrived recently (we synthesize it).
  simulatedRef: React.MutableRefObject<boolean>;
  // Current list of node ids that can receive requests (kept fresh).
  nodesRef: React.MutableRefObject<string[]>;
  isConnectedRef: React.MutableRefObject<boolean>;
}

/**
 * Watches the `dashboard` WebSocket topic for real completion events. If real
 * traffic is flowing we drive the visualization from it; otherwise we synthesize
 * a gentle, fluctuating request rate so the map is never a static mockup
 * (PRD §46 / §48 — graceful degradation + live by default).
 *
 * The returned values are refs on purpose: the 3D render loop reads them every
 * frame without triggering React re-renders.
 */
export function useLiveTraffic(providerNodeIds: string[]): LiveTrafficRefs {
  const { subscribe, isConnected } = useWebSocket();

  const rateRef = useRef(0);
  const simulatedRef = useRef(true);
  const isConnectedRef = useRef(false);
  const nodesRef = useRef<string[]>(providerNodeIds);
  const realTimesRef = useRef<number[]>([]);

  nodesRef.current = providerNodeIds;
  isConnectedRef.current = isConnected;

  useEffect(() => {
    const unsub = subscribe("dashboard", (data: unknown) => {
      const d = data as { latency_ms?: number; event?: string };
      if (d && (typeof d.latency_ms === "number" || d.event === "request_completed")) {
        realTimesRef.current.push(performance.now());
      }
    });
    return unsub;
  }, [subscribe]);

  useEffect(() => {
    const tick = setInterval(() => {
      const now = performance.now();
      realTimesRef.current = realTimesRef.current.filter((t) => now - t < 5000);
      const real = realTimesRef.current.length / 5;

      if (real > 0.2) {
        simulatedRef.current = false;
        // Small headroom so particles keep a little visual rhythm.
        rateRef.current = real * 1.4;
      } else {
        simulatedRef.current = true;
        // Fluctuating synthetic rate 2.5 .. 7.5 req/s.
        rateRef.current = 5 + 2.5 * Math.sin(now / 3500) + Math.random() * 0.8;
      }
    }, 1000);
    return () => clearInterval(tick);
  }, []);

  return { rateRef, simulatedRef, nodesRef, isConnectedRef };
}
