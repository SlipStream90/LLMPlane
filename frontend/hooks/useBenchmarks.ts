import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

//: `RunStatus` in `models/enums.py`. Note "complete", not "completed" — the
//: previous interface used the latter, so every finished run rendered with the
//: neutral "pending" styling.
export type RunStatus = "pending" | "running" | "complete" | "failed";

//: Mirrors `schemas/benchmark.py`'s `BenchmarkRunOut` field-for-field. The
//: previous interface here (name/dataset_name/progress/results_summary)
//: matched nothing the backend ever sent.
export interface BenchmarkRun {
  id: string;
  project_id: string;
  dataset_id: string;
  status: RunStatus;
  total_items: number;
  completed_items: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

//: Mirrors `schemas/benchmark.py`'s `BenchmarkDatasetOut`. Datasets are a
//: separate aggregate from runs — `/benchmark-datasets` vs `/benchmarks`.
export interface BenchmarkDataset {
  id: string;
  project_id: string;
  name: string;
  source_format: "csv" | "json";
  row_count: number;
  columns: string[];
  created_at: string;
}

export function useBenchmarks() {
  return useQuery<BenchmarkRun[]>({
    queryKey: ["benchmarks"],
    queryFn: () => apiFetch("/benchmarks"),
  });
}

export function useBenchmark(id: string) {
  return useQuery<BenchmarkRun>({
    queryKey: ["benchmarks", id],
    queryFn: () => apiFetch(`/benchmarks/${id}`),
    enabled: !!id,
  });
}

export function useBenchmarkDatasets() {
  return useQuery<BenchmarkDataset[]>({
    queryKey: ["benchmark-datasets"],
    queryFn: () => apiFetch("/benchmark-datasets"),
  });
}

/**
 * `POST /benchmark-datasets` — multipart, fields `file` and `name`.
 *
 * `apiFetch` detects the FormData body and omits its JSON Content-Type so the
 * browser-generated multipart boundary survives.
 */
export function useUploadBenchmarkDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, name }: { file: File; name: string }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("name", name);
      return apiFetch<BenchmarkDataset>("/benchmark-datasets", {
        method: "POST",
        body: form,
        //: Uploads legitimately outlast a normal read.
        timeoutMs: 120_000,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["benchmark-datasets"] }),
  });
}

export function useDeleteBenchmarkDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/benchmark-datasets/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["benchmark-datasets"] }),
  });
}

//: Mirrors `schemas/benchmark.py`'s `BenchmarkRunCreate`.
export interface BenchmarkRunCreateInput {
  dataset_id: string;
  provider_model_ids: string[];
  prompt_version_ids?: string[];
  temperatures?: number[];
  metrics?: string[];
  judge_model_id?: string | null;
}

//: `POST /benchmarks/run` (not `/benchmarks`), JSON body, returns 202.
export function useStartBenchmarkRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: BenchmarkRunCreateInput) =>
      apiFetch<BenchmarkRun>("/benchmarks/run", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["benchmarks"] }),
  });
}
