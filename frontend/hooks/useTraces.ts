import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Trace {
  id: string;
  model: string;
  latency_ms: number;
  status: "success" | "error";
  cost: number;
  tokens_input: number;
  tokens_output: number;
  timestamp: string;
  spans: Span[];
}

export interface Span {
  id: string;
  name: string;
  duration_ms: number;
  status: "ok" | "error";
  parent_id: string | null;
  attributes: Record<string, unknown>;
}

export function useTraces(params?: { model?: string; status?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.model) searchParams.set("model", params.model);
  if (params?.status) searchParams.set("status", params.status);

  const query = searchParams.toString();

  return useQuery<Trace[]>({
    queryKey: ["traces", params],
    queryFn: () => apiFetch(`/traces${query ? `?${query}` : ""}`),
  });
}

export function useTrace(id: string) {
  return useQuery<Trace>({
    queryKey: ["traces", id],
    queryFn: () => apiFetch(`/traces/${id}`),
    enabled: !!id,
  });
}
