import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Benchmark {
  id: string;
  name: string;
  dataset_name: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  total_items: number;
  processed_items: number;
  results_summary: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export function useBenchmarks() {
  return useQuery<Benchmark[]>({
    queryKey: ["benchmarks"],
    queryFn: () => apiFetch("/benchmarks"),
  });
}

export function useBenchmark(id: string) {
  return useQuery<Benchmark>({
    queryKey: ["benchmarks", id],
    queryFn: () => apiFetch(`/benchmarks/${id}`),
    enabled: !!id,
  });
}

export function useCreateBenchmark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: FormData) =>
      apiFetch("/benchmarks", {
        method: "POST",
        body: data,
        headers: {},
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["benchmarks"] }),
  });
}

export function useDeleteBenchmark() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/benchmarks/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["benchmarks"] }),
  });
}
