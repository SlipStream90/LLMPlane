import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { apiFetch } from "@/lib/api";

interface PaginatedResponse<T> {
  items: T[];
  next_cursor: string | null;
  total: number;
}

interface UsePaginatedQueryOptions<T> {
  endpoint: string;
  pageSize?: number;
  enabled?: boolean;
}

export function usePaginatedQuery<T>({
  endpoint,
  pageSize = 20,
  enabled = true,
}: UsePaginatedQueryOptions<T>) {
  const [cursor, setCursor] = useState<string | null>(null);

  const queryKey = [endpoint, cursor, pageSize];
  const queryFn = useCallback(() => {
    const params = new URLSearchParams();
    if (cursor) params.set("cursor", cursor);
    params.set("limit", String(pageSize));
    return apiFetch<PaginatedResponse<T>>(`${endpoint}?${params.toString()}`);
  }, [endpoint, cursor, pageSize]);

  const query = useQuery<PaginatedResponse<T>>({
    queryKey,
    queryFn,
    enabled,
  });

  return {
    ...query,
    items: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    hasNextPage: !!query.data?.next_cursor,
    nextPage: () => {
      if (query.data?.next_cursor) {
        setCursor(query.data.next_cursor);
      }
    },
    goToFirstPage: () => setCursor(null),
  };
}
