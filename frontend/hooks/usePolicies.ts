import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

//: `RoutingStrategy` in `models/enums.py`.
export type RoutingStrategy =
  | "cheapest"
  | "fastest"
  | "fallback"
  | "round_robin"
  | "weighted"
  | "cost_threshold"
  | "latency_threshold";

/**
 * Mirrors `schemas/routing.py`'s `RoutingPolicyOut`.
 *
 * The previous interface (type/status/rules/model_mapping) matched nothing the
 * backend sends, and every path here pointed at `/routing/policies` while the
 * router is mounted at `/routing-policies` — so all five hooks 404'd.
 */
export interface Policy {
  id: string;
  project_id: string;
  name: string;
  strategy: RoutingStrategy;
  config: Record<string, unknown>;
  model_allowlist: string[];
  is_active: boolean;
  created_at: string;
}

export interface PolicyActivated extends Policy {
  //: "applied" — gateway hot-reloaded. "deferred" — takes effect on restart.
  gateway_config_status: string;
  gateway_detail: string | null;
}

export interface PolicyCreateInput {
  name: string;
  strategy: RoutingStrategy;
  config?: Record<string, unknown>;
  model_allowlist?: string[];
}

export interface PolicyUpdateInput {
  name?: string;
  strategy?: RoutingStrategy;
  config?: Record<string, unknown>;
  model_allowlist?: string[];
}

export function usePolicies() {
  return useQuery<Policy[]>({
    queryKey: ["policies"],
    queryFn: () => apiFetch("/routing-policies"),
  });
}

export function useActivePolicy() {
  return useQuery<Policy | null>({
    queryKey: ["policies", "active"],
    queryFn: () => apiFetch("/routing-policies/active"),
  });
}

export function usePolicy(id: string) {
  return useQuery<Policy>({
    queryKey: ["policies", id],
    queryFn: () => apiFetch(`/routing-policies/${id}`),
    enabled: !!id,
  });
}

export function useCreatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PolicyCreateInput) =>
      apiFetch<Policy>("/routing-policies", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
}

export function useUpdatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: PolicyUpdateInput & { id: string }) =>
      apiFetch<Policy>(`/routing-policies/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
}

//: `POST /routing-policies/{id}/activate` — exactly one policy is active at a
//: time, so this is not the same as PATCHing `is_active`.
export function useActivatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<PolicyActivated>(`/routing-policies/${id}/activate`, {
        method: "POST",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
}

export function useDeletePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/routing-policies/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
}
