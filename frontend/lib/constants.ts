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

/** Sidebar grouping. Fourteen flat entries had no visual hierarchy — these are
 *  four distinct jobs (run the fleet, build on it, measure it, watch it). */
export type NavGroup = "Operate" | "Build" | "Evaluate" | "Observe";

export const NAV_GROUP_ORDER: NavGroup[] = ["Operate", "Build", "Evaluate", "Observe"];

export interface NavItem {
  label: string;
  href: string;
  icon: string;
  group: NavGroup;
  badge?: number;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: "LayoutDashboard", group: "Operate" },
  { label: "Command Center", href: "/infrastructure", icon: "Network", group: "Operate" },
  { label: "Providers", href: "/providers", icon: "Server", group: "Operate" },
  { label: "Deployments", href: "/deployments", icon: "Container", group: "Operate" },
  { label: "Routing", href: "/routing", icon: "GitBranch", group: "Operate" },

  { label: "Playground", href: "/playground", icon: "Play", group: "Build" },
  { label: "Prompts", href: "/prompts", icon: "FileText", group: "Build" },

  { label: "Experiments", href: "/experiments", icon: "FlaskConical", group: "Evaluate" },
  { label: "Benchmarks", href: "/benchmarks", icon: "Trophy", group: "Evaluate" },
  { label: "Evaluations", href: "/evaluations", icon: "CheckCircle", group: "Evaluate" },
  { label: "Leaderboard", href: "/leaderboard", icon: "Medal", group: "Evaluate" },

  { label: "Observability", href: "/observability", icon: "Eye", group: "Observe" },
  { label: "Logs", href: "/logs", icon: "ScrollText", group: "Observe" },
  { label: "Cost Analytics", href: "/cost-analytics", icon: "DollarSign", group: "Observe" },
];

/**
 * Categorical series palette, matching the `--color-chart-*` scale in
 * globals.css. ECharts needs concrete values rather than CSS custom properties,
 * so these are the resolved oklch equivalents of those tokens.
 *
 * Ordered so that adjacent series differ in hue AND lightness — the previous
 * list put blue (#3B82F6) next to violet (#8B5CF6) and teal (#06B6D4) next to
 * green (#10B981), pairs that are hard to separate with a red-green or
 * blue-yellow colour vision deficiency.
 */
export const CHART_COLORS = [
  "#5b8def", // blue
  "#3fbf80", // green
  "#e0a13a", // amber
  "#d968a4", // magenta
  "#4bb8c9", // cyan
  "#e5624f", // red
  "#9b7ede", // violet
  "#8fbf5a", // olive
  "#4a90d9", // steel
  "#c98a4b", // clay
];

export const TIME_RANGES = [
  { label: "Last 24h", value: "24h" },
  { label: "Last 7d", value: "7d" },
  { label: "Last 30d", value: "30d" },
  { label: "Last 90d", value: "90d" },
] as const;

export type TimeRange = (typeof TIME_RANGES)[number]["value"];
