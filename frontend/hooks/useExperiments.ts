import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Experiment {
  id: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed";
  runs_count: number;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export function useExperiments() {
  return useQuery<Experiment[]>({
    queryKey: ["experiments"],
    queryFn: () => apiFetch("/experiments"),
  });
}

export function useExperiment(id: string) {
  return useQuery<Experiment>({
    queryKey: ["experiments", id],
    queryFn: () => apiFetch(`/experiments/${id}`),
    enabled: !!id,
  });
}

export function useCreateExperiment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<Experiment, "id" | "created_at" | "updated_at">) =>
      apiFetch("/experiments", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["experiments"] }),
  });
}

export function useDeleteExperiment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/experiments/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["experiments"] }),
  });
}
