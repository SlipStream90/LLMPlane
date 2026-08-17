import type { DashboardSummaryLike, InfraEdge, InfraNode, NodeState } from "./types";

const LOCAL_PROVIDER_TYPES = new Set(["ollama", "vllm"]);

function healthToState(
  health: string | undefined,
  active: boolean | undefined
): NodeState {
  if (active === false) return "offline";
  switch (health) {
    case "healthy":
      return "healthy";
    case "degraded":
      return "warning";
    case "down":
      return "critical";
    default:
      return "offline";
  }
}

function deploymentToState(status: string | undefined): NodeState {
  switch (status) {
    case "running":
      return "healthy";
    case "starting":
      return "high-load";
    case "error":
      return "critical";
    case "stopped":
      return "offline";
    default:
      return "offline";
  }
}

interface ProviderLike {
  id: string;
  provider_type: string;
  display_name: string;
  health_status?: string;
  is_active?: boolean;
  last_latency_ms?: number | null;
}
interface DeploymentLike {
  id: string;
  model_ref: string;
  backend_type: string;
  status: string;
  port?: number | null;
  gpu_index?: number | null;
  config?: Record<string, unknown> | null;
}

export interface BuildInput {
  providers?: ProviderLike[];
  deployments?: DeploymentLike[];
  summary?: DashboardSummaryLike | null;
}

export interface BuildResult {
  nodes: InfraNode[];
  edges: InfraEdge[];
  providerNodeIds: string[];
  /** No providers and no deployments — the backbone is all that is left to draw. */
  isEmpty: boolean;
}

export function buildTopology({
  providers = [],
  deployments = [],
  summary,
}: BuildInput): BuildResult {
  /*
   * This function used to substitute a hardcoded DEMO_PROVIDERS /
   * DEMO_DEPLOYMENTS / DEMO_SUMMARY payload whenever providers and deployments
   * were both empty, so that the view was "never an empty void".
   *
   * That was removed, for three reasons:
   *
   *   1. The guard was `providers.length === 0 && deployments.length === 0`,
   *      and both parameters default to `[]`. So it fired not only for a fresh
   *      project but also while the queries were still in flight, and on any
   *      error — including a 401. A broken connection rendered as a healthy
   *      fleet.
   *   2. `DEMO_SUMMARY` was applied with `??`, so a real (zeroed) summary got
   *      grafted onto four fake providers — a mix of true and invented numbers
   *      in the same header.
   *   3. Nothing in the UI marked any of it as fake. An empty install showed
   *      "$184.27 spent today, 48,213 requests, OpenAI/Anthropic/Gemini/Groq
   *      healthy". A control plane that invents infrastructure is worse than
   *      one that shows nothing.
   *
   * `isEmpty` is returned instead, and the caller renders an honest empty
   * state that explains what to connect.
   */
  const effProviders = providers;
  const effDeployments = deployments;
  const effSummary = summary;

  const nodes: InfraNode[] = [];
  const edges: InfraEdge[] = [];

  // ---- Static backbone -------------------------------------------------
  const gpuUtil = effSummary?.gpu_util_pct_avg;
  const gpuState: NodeState =
    gpuUtil == null ? "healthy" : gpuUtil > 90 ? "critical" : gpuUtil > 75 ? "warning" : "healthy";

  nodes.push(
    {
      id: "clients",
      label: "Clients",
      kind: "clients",
      position: [-11, 0, 0],
      state: "healthy",
      metrics: {
        traffic: effSummary ? `${effSummary.requests_per_minute}/min` : "—",
      },
    },
    {
      id: "gateway",
      label: "API Gateway",
      kind: "gateway",
      position: [-6.5, 0, 0],
      state: "healthy",
      metrics: {
        "Requests / min": effSummary?.requests_per_minute ?? "—",
        "Avg latency": effSummary ? `${Math.round(effSummary.avg_latency_ms)} ms` : "—",
        "Success rate": effSummary ? `${effSummary.success_rate_pct.toFixed(1)}%` : "—",
      },
    },
    {
      id: "evaluation",
      label: "Evaluation",
      kind: "evaluation",
      position: [5, 3.5, -1.5],
      state: "healthy",
      metrics: { role: "quality scoring" },
    },
    {
      id: "cache",
      label: "Cache / Redis",
      kind: "cache",
      position: [5, -2.5, 2],
      state: "healthy",
      metrics: { role: "response cache" },
    },
    {
      id: "observability",
      label: "Observability",
      kind: "observability",
      position: [5.5, 5, -1.5],
      state: "healthy",
      metrics: { role: "metrics · traces · logs" },
    },
    {
      id: "database",
      label: "Database",
      kind: "database",
      position: [11, 0, 0],
      state: "healthy",
      metrics: {
        requests: effSummary ? effSummary.requests_today : "—",
        cost: effSummary ? `$${effSummary.cost_today_usd.toFixed(2)}` : "—",
      },
    },
    {
      id: "gpu",
      label: "GPU",
      kind: "gpu",
      position: [-6.5, -4.5, 0],
      state: gpuState,
      metrics: {
        utilization: gpuUtil == null ? "n/a" : `${Math.round(gpuUtil)}%`,
        deployments: effSummary?.active_deployments ?? "—",
      },
    }
  );

  // ---- Provider + deployment (model) nodes ----------------------------
  const cloud = effProviders.filter((p) => !LOCAL_PROVIDER_TYPES.has(p.provider_type));
  const localFromProviders = effProviders.filter((p) =>
    LOCAL_PROVIDER_TYPES.has(p.provider_type)
  );

  // Prefer deployment rows for local inference; fall back to provider rows.
  const localNodes: { id: string; label: string; type: string; state: NodeState; raw: unknown; metrics: Record<string, string|number> }[] = [];
  for (const d of effDeployments) {
    localNodes.push({
      id: `dep:${d.id}`,
      label: d.model_ref,
      type: d.backend_type,
      state: deploymentToState(d.status),
      raw: d,
      metrics: {
        status: d.status,
        backend: d.backend_type,
        gpu: d.gpu_index ?? "—",
        port: d.port ?? "—",
        quantization: String((d.config as Record<string, unknown> | null)?.quantization ?? "—"),
      },
    });
  }
  for (const p of localFromProviders) {
    if (effDeployments.some((d) => d.model_ref === p.display_name)) continue;
    localNodes.push({
      id: `prov:${p.id}`,
      label: p.display_name,
      type: p.provider_type,
      state: healthToState(p.health_status, p.is_active),
      raw: p,
      metrics: { health: p.health_status ?? "unknown", latency: p.last_latency_ms ?? "—" },
    });
  }

  const modelNodes = [
    ...cloud.map((p) => ({
      id: `prov:${p.id}`,
      label: p.display_name,
      type: p.provider_type,
      state: healthToState(p.health_status, p.is_active),
      raw: p,
      metrics: {
        health: p.health_status ?? "unknown",
        latency: p.last_latency_ms ?? "—",
        type: p.provider_type,
      },
    })),
    ...localNodes,
  ];

  // Lay model nodes out vertically in the provider tier.
  const n = Math.max(modelNodes.length, 1);
  modelNodes.forEach((m, i) => {
    const y = (i - (n - 1) / 2) * 2.4;
    const z = m.type === "ollama" || m.type === "vllm" ? 2.5 : -0.5;
    const kind = m.type === "ollama" || m.type === "vllm" ? "deployment" : "provider";
    nodes.push({
      id: m.id,
      label: m.label,
      kind,
      position: [0, y, z],
      state: m.state,
      metrics: m.metrics,
      source: { type: kind === "deployment" ? "deployment" : "provider", raw: m.raw },
      providerType: m.type,
    });
    edges.push({ id: `g-${m.id}`, from: "gateway", to: m.id, kind: "request" });
    edges.push({ id: `m-${m.id}`, from: m.id, to: "evaluation", kind: "dependency" });
    edges.push({ id: `d-${m.id}`, from: m.id, to: "database", kind: "dependency" });
    if (kind === "deployment") {
      edges.push({ id: `gpu-${m.id}`, from: "gpu", to: m.id, kind: "dependency" });
    }
  });

  // ---- Backbone edges --------------------------------------------------
  edges.push({ id: "c-g", from: "clients", to: "gateway", kind: "request" });
  edges.push({ id: "g-cache", from: "gateway", to: "cache", kind: "dependency" });
  edges.push({ id: "g-obs", from: "gateway", to: "observability", kind: "dependency" });
  edges.push({ id: "e-db", from: "evaluation", to: "database", kind: "dependency" });

  const providerNodeIds = nodes
    .filter((nd) => nd.kind === "provider" || nd.kind === "deployment")
    .map((nd) => nd.id);

  return {
    nodes,
    edges,
    providerNodeIds,
    isEmpty: effProviders.length === 0 && effDeployments.length === 0,
  };
}
