import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export interface Deployment {
  id: string;
  name: string;
  backend_type: "ollama" | "vllm";
  status: "running" | "stopped" | "starting" | "error";
  endpoint: string;
  gpu_allocation: { count: number; memory_mb: number };
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export function useDeployments() {
  return useQuery<Deployment[]>({
    queryKey: ["deployments"],
    queryFn: () => apiFetch("/deployments"),
  });
}

export function useDeployment(id: string) {
  return useQuery<Deployment>({
    queryKey: ["deployments", id],
    queryFn: () => apiFetch(`/deployments/${id}`),
    enabled: !!id,
  });
}

export function useCreateDeployment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<Deployment, "id" | "created_at" | "updated_at">) =>
      apiFetch("/deployments", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["deployments"] }),
  });
}

export function useDeploymentAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "start" | "stop" | "restart" }) =>
      apiFetch(`/deployments/${id}/${action}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["deployments"] }),
  });
}

export function useDeleteDeployment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/deployments/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["deployments"] }),
  });
}
