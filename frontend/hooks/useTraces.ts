import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Trace {
  id: string;
  trace_id: string | null;
  model_id: string;
  status: "success" | "error" | "timeout";
  latency_ms: number;
  ttft_ms: number | null;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  error_message: string | null;
  tags: string[];
  requested_at: string;
}

export interface TraceQuery {
  model_id?: string;
  status?: string;
  since?: string;
  limit?: number;
}

async function fetchTraces(params?: TraceQuery): Promise<Trace[]> {
  const sp = new URLSearchParams();
  if (params?.model_id) sp.set("model_id", params.model_id);
  if (params?.status) sp.set("status", params.status);
  if (params?.since) sp.set("since", params.since);
  if (params?.limit) sp.set("limit", String(params.limit));
  const query = sp.toString();
  const res = await apiFetch<{ data: Trace[] } | Trace[]>(
    `/traces${query ? `?${query}` : ""}`
  );
  // The API returns a Page envelope; unwrap it, but tolerate a bare array too.
  return Array.isArray(res) ? res : res.data;
}

export function useTraces(params?: TraceQuery) {
  return useQuery<Trace[]>({
    queryKey: ["traces", params],
    queryFn: () => fetchTraces(params),
  });
}

export interface TraceDetail {
  request: Trace | null;
  langfuse_available: boolean;
  trace: Record<string, unknown> | null;
  detail_error: string | null;
}

export function useTraceDetail(id: string) {
  return useQuery<TraceDetail>({
    queryKey: ["trace", "detail", id],
    queryFn: () => apiFetch(`/traces/${id}`),
    enabled: !!id,
  });
}
