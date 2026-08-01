import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Policy {
  id: string;
  name: string;
  type: "fallback" | "round-robin" | "cost-optimized" | "latency-optimized";
  status: "active" | "inactive";
  rules: Record<string, unknown>[];
  model_mapping: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export function usePolicies() {
  return useQuery<Policy[]>({
    queryKey: ["policies"],
    queryFn: () => apiFetch("/routing/policies"),
  });
}

export function usePolicy(id: string) {
  return useQuery<Policy>({
    queryKey: ["policies", id],
    queryFn: () => apiFetch(`/routing/policies/${id}`),
    enabled: !!id,
  });
}

export function useCreatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<Policy, "id" | "created_at" | "updated_at">) =>
      apiFetch("/routing/policies", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
}

export function useUpdatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Policy> & { id: string }) =>
      apiFetch(`/routing/policies/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
}

export function useDeletePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/routing/policies/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });
}
