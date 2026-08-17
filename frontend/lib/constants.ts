//: Re-exported from `lib/api` so there is a single place that normalizes the
//: `/api/v1` suffix. This module used to duplicate the raw env read, which
//: meant a bare-origin `NEXT_PUBLIC_API_URL` 404'd here too.
export { API_BASE_URL } from "./api";

/**
 * WebSocket origin. `NEXT_PUBLIC_WS_URL` is documented as a bare `wss://host`,
 * so the `/ws` path is appended here rather than baked into the env var.
 */
function resolveWsUrl(): string {
  const raw = (process.env.NEXT_PUBLIC_WS_URL ?? "").trim().replace(/\/+$/, "");
  if (!raw) return "ws://localhost:8000/ws";
  return raw.endsWith("/ws") ? raw : `${raw}/ws`;
}

export const WS_BASE_URL = resolveWsUrl();

export interface NavItem {
  label: string;
  href: string;
  icon: string;
  badge?: number;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: "LayoutDashboard" },
  { label: "Command Center", href: "/infrastructure", icon: "Network" },
  { label: "Providers", href: "/providers", icon: "Server" },
  { label: "Deployments", href: "/deployments", icon: "Container" },
  { label: "Routing", href: "/routing", icon: "GitBranch" },
  { label: "Playground", href: "/playground", icon: "Play" },
  { label: "Prompts", href: "/prompts", icon: "FileText" },
  { label: "Experiments", href: "/experiments", icon: "FlaskConical" },
  { label: "Benchmarks", href: "/benchmarks", icon: "Trophy" },
  { label: "Evaluations", href: "/evaluations", icon: "CheckCircle" },
  { label: "Leaderboard", href: "/leaderboard", icon: "Medal" },
  { label: "Observability", href: "/observability", icon: "Eye" },
  { label: "Logs", href: "/logs", icon: "ScrollText" },
  { label: "Cost Analytics", href: "/cost-analytics", icon: "DollarSign" },
];

export const CHART_COLORS = [
  "#3B82F6",
  "#8B5CF6",
  "#06B6D4",
  "#10B981",
  "#F59E0B",
  "#EF4444",
  "#EC4899",
  "#6366F1",
  "#14B8A6",
  "#F97316",
];

export const TIME_RANGES = [
  { label: "Last 24h", value: "24h" },
  { label: "Last 7d", value: "7d" },
  { label: "Last 30d", value: "30d" },
  { label: "Last 90d", value: "90d" },
] as const;

export type TimeRange = (typeof TIME_RANGES)[number]["value"];
