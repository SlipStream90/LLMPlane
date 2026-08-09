"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Activity, Box, Grid3x3, Zap, Cpu, AlertTriangle } from "lucide-react";
import { useCommandCenter } from "@/hooks/useCommandCenter";
import { useCommandCenterUI } from "./store";
import { useLiveTraffic } from "./useLiveTraffic";
import { NodeInspectorPanel } from "./NodeInspectorPanel";
import { Scene2D } from "./Scene2D";
import { STATE_COLORS, STATE_LABEL } from "./InfraNodeMesh";
import type { CameraMode, NodeState } from "./types";
import { cn } from "@/lib/utils";

const Scene3D = dynamic(() => import("./Scene3D").then((m) => m.Scene3D), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full text-muted-foreground">
      Loading 3D scene…
    </div>
  ),
});

const CAMERA_MODES: { mode: CameraMode; label: string }[] = [
  { mode: "overview", label: "Overview" },
  { mode: "gateway", label: "Gateway" },
  { mode: "models", label: "Models" },
  { mode: "observability", label: "Observability" },
  { mode: "gpu", label: "GPU" },
  { mode: "deployment", label: "Deployment" },
];

const LEGEND: NodeState[] = ["healthy", "high-load", "warning", "critical", "offline"];

export function CommandCenter() {
  const { nodes, edges, providerNodeIds, summary, isLoading } = useCommandCenter();
  const { viewMode, reduceMotion, cameraMode, setViewMode, setReduceMotion, setCameraMode } =
    useCommandCenterUI();
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
  const activeProviders = nodes.filter((n) => n.kind === "provider").length;
  const alerts = nodes.filter(
    (n) => n.state === "critical" || n.state === "warning"
  ).length;

  return (
    <div className="page-container !max-w-none h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Infrastructure Command Center</h1>
          <p className="text-muted-foreground text-sm">
            Live 3D map of your LLM stack — requests, models, providers and GPUs.
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
              <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                <AlertTriangle className="w-4 h-4" />
                {alerts}
              </div>
            )}
          </div>

          {/* Live indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-muted/50 border border-border text-xs">
            <span className={cn("w-2 h-2 rounded-full", connected ? "bg-green-500 animate-pulse" : "bg-zinc-500")} />
            {simulated ? "Live (sim)" : "Live"}
          </div>

          {/* View toggle */}
          <div className="flex rounded-lg border border-border overflow-hidden">
            <button
              onClick={() => setViewMode("3d")}
              className={cn("px-3 py-1.5 text-sm flex items-center gap-1.5", viewMode === "3d" ? "bg-primary text-primary-foreground" : "hover:bg-muted")}
            >
              <Grid3x3 className="w-4 h-4" /> 3D
            </button>
            <button
              onClick={() => setViewMode("2d")}
              className={cn("px-3 py-1.5 text-sm flex items-center gap-1.5", viewMode === "2d" ? "bg-primary text-primary-foreground" : "hover:bg-muted")}
            >
              2D
            </button>
          </div>

          <button
            onClick={() => setReduceMotion(!reduceMotion)}
            className={cn("px-3 py-1.5 text-sm rounded-lg border border-border", reduceMotion ? "bg-primary/20 border-primary/50" : "hover:bg-muted")}
          >
            Reduce Motion
          </button>
        </div>
      </div>

      {/* Camera modes */}
      <div className="flex items-center gap-1.5 mb-3 flex-wrap">
        {CAMERA_MODES.map((c) => (
          <button
            key={c.mode}
            onClick={() => setCameraMode(c.mode)}
            className={cn(
              "px-3 py-1 text-xs rounded-full border transition-colors",
              cameraMode === c.mode
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border hover:bg-muted text-muted-foreground"
            )}
          >
            {c.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-3">
          {LEGEND.map((s) => (
            <span key={s} className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: STATE_COLORS[s] }} />
              {STATE_LABEL[s]}
            </span>
          ))}
        </div>
      </div>

      {/* Scene */}
      <div className="relative flex-1 rounded-xl border border-border overflow-hidden bg-[#05070d] min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            Loading infrastructure state…
          </div>
        ) : viewMode === "3d" ? (
          <Scene3D
            nodes={nodes}
            edges={edges}
            selectedId={selectedId}
            hoveredId={hoveredId}
            cameraMode={cameraMode}
            reduceMotion={reduceMotion}
            onSelect={(id) => setSelectedId(id)}
            onHover={setHoveredId}
            traffic={traffic}
          />
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
    <div className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-muted/40 border border-border">
      <span className="text-primary">{icon}</span>
      <div className="leading-tight">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="text-sm font-semibold font-mono">{value}</p>
      </div>
    </div>
  );
}
