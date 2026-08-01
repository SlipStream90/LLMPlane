import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { TimeRange } from "@/lib/constants";

export interface DashboardData {
  kpis: {
    total_requests: number;
    total_cost: number;
    avg_latency_ms: number;
    error_rate: number;
  };
  request_over_time: { timestamp: string; count: number }[];
  cost_over_time: { timestamp: string; cost: number }[];
  latency_histogram: { bucket: string; count: number }[];
  model_usage: { model: string; requests: number; cost: number }[];
}

export function useDashboard(timeRange: TimeRange = "24h") {
  return useQuery<DashboardData>({
    queryKey: ["dashboard", timeRange],
    queryFn: () => apiFetch(`/dashboard?range=${timeRange}`),
  });
}
