import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { TimeRange } from "@/lib/constants";
import type { TimeseriesResponse } from "./useDashboard";

//: Mirrors `schemas/analytics.py`'s `CostBreakdownItem` / `CostBreakdownResponse`.
export interface CostBreakdownItem {
  key: string;
  cost_usd: number;
  request_count: number;
}

export interface CostBreakdownResponse {
  dimension: string;
  since: string;
  until: string;
  total_cost_usd: number;
  items: CostBreakdownItem[];
}

//: Mirrors `schemas/analytics.py`'s `CostForecast`.
export interface CostForecast {
  method: string;
  days_observed: number;
  avg_daily_cost_usd: number;
  projected_month_end_usd: number;
}

//: `Dimension` in `api/v1/cost_analytics.py`.
export type CostDimension = "model" | "provider" | "day" | "tag";

const RANGE_DAYS: Record<TimeRange, number> = {
  "24h": 1,
  "7d": 7,
  "30d": 30,
  "90d": 90,
};

export function daysForRange(timeRange: TimeRange): number {
  return RANGE_DAYS[timeRange] ?? 30;
}

export function useCostBreakdown(
  timeRange: TimeRange = "30d",
  dimension: CostDimension = "model"
) {
  const days = daysForRange(timeRange);
  return useQuery<CostBreakdownResponse>({
    queryKey: ["cost", "breakdown", days, dimension],
    queryFn: () => apiFetch(`/cost/breakdown?days=${days}&dimension=${dimension}`),
  });
}

export function useCostOverTime(timeRange: TimeRange = "30d") {
  const days = daysForRange(timeRange);
  //: `/cost/over-time` only accepts hour|day; hourly buckets over 90 days
  //: would be 2160 points, so anything past a day uses daily granularity.
  const granularity = days <= 1 ? "hour" : "day";
  return useQuery<TimeseriesResponse>({
    queryKey: ["cost", "over-time", days, granularity],
    queryFn: () =>
      apiFetch(`/cost/over-time?days=${days}&granularity=${granularity}`),
  });
}

export function useCostForecast(lookbackDays = 14) {
  return useQuery<CostForecast>({
    queryKey: ["cost", "forecast", lookbackDays],
    queryFn: () => apiFetch(`/cost/forecast?lookback_days=${lookbackDays}`),
  });
}
