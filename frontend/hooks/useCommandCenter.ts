"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useProviders, type Provider } from "@/hooks/useProviders";
import { useDeployments, type Deployment } from "@/hooks/useDeployments";
import { buildTopology } from "@/components/command-center/topology";
import type { DashboardSummaryLike } from "@/components/command-center/types";

export function useCommandCenter() {
  const providers = useProviders();
  const deployments = useDeployments();
  const summary = useQuery<DashboardSummaryLike>({
    queryKey: ["dashboard", "summary"],
    queryFn: () => apiFetch("/dashboard/summary"),
    refetchInterval: 15000,
  });

  const { nodes, edges, providerNodeIds } = useMemo(
    () =>
      buildTopology({
        providers: providers.data as Provider[] | undefined,
        deployments: deployments.data as Deployment[] | undefined,
        summary: summary.data,
      }),
    [providers.data, deployments.data, summary.data]
  );

  return {
    nodes,
    edges,
    providerNodeIds,
    summary: summary.data ?? null,
    isLoading: providers.isLoading && deployments.isLoading,
  };
}
