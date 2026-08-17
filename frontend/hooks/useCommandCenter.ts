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

  const { nodes, edges, providerNodeIds, isEmpty } = useMemo(
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
    isEmpty,
    summary: summary.data ?? null,
    // `&&` meant the view rendered as "loaded but empty" while one of the two
    // queries was still in flight — which, with the old demo fallback, briefly
    // painted a fake fleet. Either query still loading means still loading.
    isLoading: providers.isLoading || deployments.isLoading,
    isError: providers.isError || deployments.isError,
    error: providers.error ?? deployments.error,
  };
}
