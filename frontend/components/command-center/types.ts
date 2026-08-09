// Shared types for the 3D / 2D infrastructure Command Center.

export type NodeState =
  | "healthy"
  | "high-load"
  | "warning"
  | "critical"
  | "offline";

export type NodeKind =
  | "clients"
  | "gateway"
  | "provider"
  | "deployment"
  | "evaluation"
  | "cache"
  | "database"
  | "observability"
  | "gpu";

export interface InfraNode {
  id: string;
  label: string;
  kind: NodeKind;
  position: [number, number, number];
  state: NodeState;
  // Optional real-ish metrics surfaced in the inspector panel.
  metrics: Record<string, string | number>;
  // Where this node gets its real backing from, for the inspector.
  source?: {
    type: "provider" | "deployment" | "static";
    raw: unknown;
  };
  providerType?: string;
}

export interface InfraEdge {
  id: string;
  from: string;
  to: string;
  // "request" edges animate particles; "dependency" edges are static links.
  kind: "request" | "dependency";
}

export type CameraMode =
  | "overview"
  | "gateway"
  | "models"
  | "observability"
  | "gpu"
  | "deployment";

export interface LiveRequest {
  id: number;
  providerId: string;
  status: "success" | "error" | "timeout";
  latencyMs: number;
  // 0..1 progress used by the particle system; purely visual.
  bornAt: number;
}

export interface InfraSnapshot {
  nodes: InfraNode[];
  edges: InfraEdge[];
  // Map of providerId -> node id, so live requests know where to route.
  providerNodeIds: string[];
  requestRatePerSec: number;
  simulated: boolean;
  summary: DashboardSummaryLike | null;
}

export interface DashboardSummaryLike {
  requests_today: number;
  cost_today_usd: number;
  avg_latency_ms: number;
  success_rate_pct: number;
  error_rate_pct: number;
  tokens_used_today: number;
  requests_per_minute: number;
  active_deployments: number;
  gpu_util_pct_avg: number | null;
}
