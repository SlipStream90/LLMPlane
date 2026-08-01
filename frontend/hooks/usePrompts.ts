import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Prompt {
  id: string;
  name: string;
  description: string;
  template: string;
  variables: string[];
  version: number;
  versions: { version: number; template: string; created_at: string }[];
  created_at: string;
  updated_at: string;
}

export function usePrompts() {
  return useQuery<Prompt[]>({
    queryKey: ["prompts"],
    queryFn: () => apiFetch("/prompts"),
  });
}

export function usePrompt(id: string) {
  return useQuery<Prompt>({
    queryKey: ["prompts", id],
    queryFn: () => apiFetch(`/prompts/${id}`),
    enabled: !!id,
  });
}

export function useCreatePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<Prompt, "id" | "created_at" | "updated_at" | "versions">) =>
      apiFetch("/prompts", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useUpdatePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Prompt> & { id: string }) =>
      apiFetch(`/prompts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}

export function useDeletePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/prompts/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}
