export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
export const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:4000";

export interface NavItem {
  label: string;
  href: string;
  icon: string;
  badge?: number;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: "LayoutDashboard" },
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
