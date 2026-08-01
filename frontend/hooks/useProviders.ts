import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Provider {
  id: string;
  name: string;
  type: string;
  status: "healthy" | "degraded" | "down";
  models: string[];
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export function useProviders() {
  return useQuery<Provider[]>({
    queryKey: ["providers"],
    queryFn: () => apiFetch("/providers"),
  });
}

export function useProvider(id: string) {
  return useQuery<Provider>({
    queryKey: ["providers", id],
    queryFn: () => apiFetch(`/providers/${id}`),
    enabled: !!id,
  });
}

export function useCreateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<Provider, "id" | "created_at" | "updated_at">) =>
      apiFetch("/providers", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });
}

export function useUpdateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Provider> & { id: string }) =>
      apiFetch(`/providers/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });
}

export function useDeleteProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/providers/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });
}
