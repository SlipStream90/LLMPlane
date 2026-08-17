import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { TimeRange } from "@/lib/constants";

//: Mirrors `schemas/analytics.py`'s `ModelUsage`.
export interface ModelUsage {
  model_id: string;
  request_count: number;
  cost_usd: number;
  tokens: number;
}

//: Mirrors `schemas/analytics.py`'s `ProviderUsage`.
export interface ProviderUsage {
  provider_type: string;
  request_count: number;
  cost_usd: number;
}

/**
 * Mirrors `schemas/analytics.py`'s `DashboardSummary`.
 *
 * The previous `DashboardData` interface here (kpis/request_over_time/
 * cost_over_time/latency_histogram) described a response the backend has never
 * sent, and was fetched from `GET /dashboard` — a route that does not exist.
 * Every field read off it was undefined even when the request succeeded.
 */
export interface DashboardSummary {
  requests_today: number;
  cost_today_usd: number;
  avg_latency_ms: number;
  success_rate_pct: number;
  error_rate_pct: number;
  tokens_used_today: number;
  requests_per_minute: number;
  model_usage: ModelUsage[];
  provider_usage: ProviderUsage[];
  active_deployments: number;
  gpu_util_pct_avg: number | null;
}

//: Mirrors `schemas/analytics.py`'s `TimeseriesPoint`.
export interface TimeseriesPoint {
  bucket: string;
  request_count: number;
  cost_usd: number;
  avg_latency_ms: number;
  tokens: number;
  error_count: number;
}

export interface TimeseriesResponse {
  granularity: string;
  since: string;
  until: string;
  points: TimeseriesPoint[];
}

export interface ErrorReason {
  reason: string;
  count: number;
}

const RANGE_HOURS: Record<TimeRange, number> = {
  "24h": 24,
  "7d": 24 * 7,
  "30d": 24 * 30,
  "90d": 24 * 90,
};

//: `/dashboard/error-reasons` caps `hours` at 720; 90d would 422 without this.
const ERROR_REASON_MAX_HOURS = 720;

//: `/dashboard/timeseries` caps `hours` at 8760 and only accepts these three
//: granularities; picking one per range keeps the bucket count sane.
function granularityFor(hours: number): "minute" | "hour" | "day" {
  if (hours <= 2) return "minute";
  if (hours <= 24 * 3) return "hour";
  return "day";
}

export function useDashboard() {
  return useQuery<DashboardSummary>({
    queryKey: ["dashboard", "summary"],
    queryFn: () => apiFetch("/dashboard/summary"),
  });
}

export function useDashboardTimeseries(timeRange: TimeRange = "24h") {
  const hours = RANGE_HOURS[timeRange] ?? 24;
  const granularity = granularityFor(hours);
  return useQuery<TimeseriesResponse>({
    queryKey: ["dashboard", "timeseries", hours, granularity],
    queryFn: () =>
      apiFetch(`/dashboard/timeseries?hours=${hours}&granularity=${granularity}`),
  });
}

export function useErrorReasons(timeRange: TimeRange = "24h") {
  const hours = Math.min(RANGE_HOURS[timeRange] ?? 24, ERROR_REASON_MAX_HOURS);
  return useQuery<ErrorReason[]>({
    queryKey: ["dashboard", "error-reasons", hours],
    queryFn: () => apiFetch(`/dashboard/error-reasons?hours=${hours}`),
  });
}
