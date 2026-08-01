"use client";

import { useQuery } from "@tanstack/react-query";
import { API_BASE, cn } from "@/lib/utils";

async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => fetchApi<any>("/dashboard/summary"),
    refetchInterval: 5000,
  });
}

export function useDashboardTimeseries(period: string = "24h") {
  return useQuery({
    queryKey: ["dashboard", "timeseries", period],
    queryFn: () => fetchApi<any>(`/dashboard/timeseries?period=${period}`),
    refetchInterval: 30000,
  });
}

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => fetchApi<any>("/providers"),
  });
}

export function useDeployments() {
  return useQuery({
    queryKey: ["deployments"],
    queryFn: () => fetchApi<any>("/deployments"),
  });
}

export function useRoutingPolicies() {
  return useQuery({
    queryKey: ["routing-policies"],
    queryFn: () => fetchApi<any>("/routing-policies"),
  });
}

export function useLeaderboard(sortBy: string = "judge_score") {
  return useQuery({
    queryKey: ["leaderboard", sortBy],
    queryFn: () => fetchApi<any>(`/leaderboard?sort_by=${sortBy}`),
  });
}

export function useTraces() {
  return useQuery({
    queryKey: ["traces"],
    queryFn: () => fetchApi<any>("/traces"),
  });
}

export function useCostAnalytics(period: string = "30d") {
  return useQuery({
    queryKey: ["cost-analytics", period],
    queryFn: () => fetchApi<any>(`/cost-analytics?period=${period}`),
  });
}
