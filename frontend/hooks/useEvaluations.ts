import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Evaluation {
  id: string;
  benchmark_id: string;
  experiment_id: string;
  model: string;
  prompt_name: string;
  metrics: Record<string, number>;
  score: number;
  created_at: string;
}

export function useEvaluations(params?: {
  benchmark_id?: string;
  experiment_id?: string;
  model?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.benchmark_id) searchParams.set("benchmark_id", params.benchmark_id);
  if (params?.experiment_id) searchParams.set("experiment_id", params.experiment_id);
  if (params?.model) searchParams.set("model", params.model);

  const query = searchParams.toString();

  return useQuery<Evaluation[]>({
    queryKey: ["evaluations", params],
    queryFn: () => apiFetch(`/evaluations${query ? `?${query}` : ""}`),
  });
}

export function useEvaluation(id: string) {
  return useQuery<Evaluation>({
    queryKey: ["evaluations", id],
    queryFn: () => apiFetch(`/evaluations/${id}`),
    enabled: !!id,
  });
}
