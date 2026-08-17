"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Activity, Box, Zap, Cpu, AlertTriangle } from "lucide-react";
import { useCommandCenter } from "@/hooks/useCommandCenter";
import { useCommandCenterUI } from "./store";
import { useLiveTraffic } from "./useLiveTraffic";
import { NodeInspectorPanel } from "./NodeInspectorPanel";
import { Scene2D } from "./Scene2D";
import { STATE_COLORS, STATE_LABEL } from "./node-state";
import type { NodeState } from "./types";
import { cn } from "@/lib/utils";


const LEGEND: NodeState[] = ["healthy", "high-load", "warning", "critical", "offline"];

export function CommandCenter() {
  const { nodes, edges, providerNodeIds, summary, isLoading, isEmpty, isError, error } =
    useCommandCenter();
  const { reduceMotion, setReduceMotion } = useCommandCenterUI();
  const traffic = useLiveTraffic(providerNodeIds);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [simulated, setSimulated] = useState(true);
  const [connected, setConnected] = useState(false);

  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null;
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;

  useEffect(() => {
    const t = setInterval(() => {
      setSimulated(traffic.simulatedRef.current);
      setConnected(traffic.isConnectedRef.current);
    }, 1500);
    return () => clearInterval(t);
  }, [traffic]);

  const activeModels = nodes.filter(
    (n) => (n.kind === "provider" || n.kind === "deployment") && n.state === "healthy"
  ).length;
  const alerts = nodes.filter(
    (n) => n.state === "critical" || n.state === "warning"
  ).length;

  return (
    <div className="page-container !max-w-none h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <h1 className="text-[1.375rem] font-semibold tracking-tight">Command Center</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Live map of your LLM stack — providers, deployments and GPUs.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* KPI chips */}
          <div className="hidden lg:flex items-center gap-2 mr-2">
            <Kpi icon={<Activity className="w-4 h-4" />} label="Req/min" value={summary?.requests_per_minute ?? "—"} />
            <Kpi icon={<Zap className="w-4 h-4" />} label="Latency" value={summary ? `${Math.round(summary.avg_latency_ms)}ms` : "—"} />
            <Kpi icon={<Box className="w-4 h-4" />} label="Models" value={activeModels} />
            <Kpi icon={<Cpu className="w-4 h-4" />} label="GPU" value={summary?.gpu_util_pct_avg == null ? "n/a" : `${Math.round(summary.gpu_util_pct_avg)}%`} />
            {alerts > 0 && (
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-danger-subtle border border-danger/25 text-danger text-sm">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span className="tabular">{alerts}</span>
              </div>
            )}
          </div>

          {/*
            The particle flow is driven by real `dashboard`-topic WebSocket
            events when they arrive, and by a synthetic rate when they do not.
            "Live (sim)" read as a variant of live; it is the opposite, so the
            two states are now named for what they are.
          */}
          <div
            title={
              simulated
                ? "No request events are arriving, so the flow animation is synthetic. Request telemetry requires a gateway publishing to the requests:completed stream."
                : "Particle flow is driven by live request events."
            }
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-surface-2 border border-border text-xs"
          >
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full",
                !connected ? "bg-subtle-foreground" : simulated ? "bg-warning" : "bg-success"
              )}
            />
            {!connected ? "Disconnected" : simulated ? "Simulated flow" : "Live traffic"}
          </div>

          <button
            onClick={() => setReduceMotion(!reduceMotion)}
            aria-pressed={reduceMotion}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md border transition-colors",
              reduceMotion
                ? "bg-primary-subtle border-primary/40 text-primary"
                : "border-border text-muted-foreground hover:bg-surface-2 hover:text-foreground"
            )}
          >
            Reduce motion
          </button>
        </div>
      </div>

      {/* Legend.
          The Overview/Gateway/Models/GPU camera pills that used to sit here
          were removed: `cameraMode` was persisted to the store and drove their
          highlight state, but it was never passed to Scene2D, so clicking them
          changed nothing on screen. A control that looks live and does nothing
          is worse than no control. The store field is retained for the focus
          implementation to hang off. */}
      <div className="flex items-center gap-3 mb-3 flex-wrap justify-end">
        {LEGEND.map((s) => (
          <span key={s} className="flex items-center gap-1 text-[11px] text-muted-foreground">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: STATE_COLORS[s] }} />
            {STATE_LABEL[s]}
          </span>
        ))}
      </div>

      {/* Scene */}
      <div className="relative flex-1 rounded-lg border border-border overflow-hidden bg-background-subtle min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            Loading infrastructure state…
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <p className="font-medium text-danger">Could not reach the control plane</p>
            <p className="text-sm text-muted-foreground mt-1.5 max-w-md">
              {error instanceof Error ? error.message : "The providers and deployments queries failed."}
            </p>
          </div>
        ) : isEmpty ? (
          /* Previously this branch rendered four fabricated providers and two
             fabricated deployments with invented traffic figures. */
          <div className="grid-bg flex flex-col items-center justify-center h-full text-center px-6">
            <p className="font-medium">No infrastructure connected yet</p>
            <p className="text-sm text-muted-foreground mt-1.5 max-w-md">
              Connect a provider or deploy a model and it will appear on this map with live
              health, latency and GPU state.
            </p>
            <div className="flex items-center gap-2 mt-4">
              <Link
                href="/providers"
                className="px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary-hover transition-colors"
              >
                Connect a provider
              </Link>
              <Link
                href="/deployments/new"
                className="px-3.5 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors"
              >
                Deploy a model
              </Link>
            </div>
          </div>
        ) : (
          <Scene2D
            nodes={nodes}
            edges={edges}
            selectedId={selectedId}
            hoveredId={hoveredId}
            reduceMotion={reduceMotion}
            onSelect={(id) => setSelectedId(id)}
            onHover={setHoveredId}
            traffic={traffic}
          />
        )}

        <NodeInspectorPanel node={selectedNode} onClose={() => setSelectedId(null)} />
      </div>
    </div>
  );
}

function Kpi({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-md bg-surface-2 border border-border">
      <span className="text-primary">{icon}</span>
      <div className="leading-tight">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="text-sm font-semibold font-mono">{value}</p>
      </div>
    </div>
  );
}
