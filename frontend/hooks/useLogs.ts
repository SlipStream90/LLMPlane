import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface LogEntry {
  timestamp: string | null;
  level: string | null;
  service: string | null;
  request_id: string | null;
  trace_id: string | null;
  provider: string | null;
  model: string | null;
  message: string | null;
  extra: Record<string, unknown>;
}

export interface LogFilters {
  q?: string;
  level?: string;
  service?: string;
  provider?: string;
  model?: string;
  request_id?: string;
  trace_id?: string;
  limit?: number;
}

export function useLogs(filters: LogFilters, live = false) {
  const sp = new URLSearchParams();
  if (filters.q) sp.set("q", filters.q);
  if (filters.level) sp.set("level", filters.level);
  if (filters.service) sp.set("service", filters.service);
  if (filters.provider) sp.set("provider", filters.provider);
  if (filters.model) sp.set("model", filters.model);
  if (filters.request_id) sp.set("request_id", filters.request_id);
  if (filters.trace_id) sp.set("trace_id", filters.trace_id);
  sp.set("limit", String(filters.limit ?? 500));

  return useQuery<LogEntry[]>({
    queryKey: ["logs", filters, live],
    queryFn: () => apiFetch(`/logs?${sp.toString()}`),
    // "Live" polls on a short interval; PRD §46 allows polling as the
    // WebSocket/SSE fallback when streaming is unavailable.
    refetchInterval: live ? 2000 : false,
  });
}
