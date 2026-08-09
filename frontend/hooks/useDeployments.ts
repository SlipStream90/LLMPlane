import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export type DeploymentStatus =
  | "pending"
  | "downloading"
  | "running"
  | "stopped"
  | "error"
  | "deleting";

export interface Deployment {
  id: string;
  project_id: string;
  provider_id: string;
  backend_type: "ollama" | "vllm";
  model_ref: string;
  status: DeploymentStatus;
  container_id: string | null;
  gpu_index: number | null;
  port: number | null;
  error_message: string | null;
  download_progress_pct: number | null;
  config: Record<string, unknown> | null;
  created_at: string;
}

export interface DeploymentBackendOption {
  backend_type: string;
  image: string;
  requires_gpu: boolean;
  available: boolean;
}

export interface CreateDeploymentInput {
  backend_type: "ollama" | "vllm";
  model_ref: string;
  gpu_index?: number | null;
  config?: Record<string, unknown> | null;
}

export function useDeployments() {
  return useQuery<Deployment[]>({
    queryKey: ["deployments"],
    queryFn: () => apiFetch("/deployments"),
  });
}

export function useDeploymentBackends() {
  return useQuery<{ gpu_available: boolean; backends: DeploymentBackendOption[] }>({
    queryKey: ["deployments", "backends"],
    queryFn: () => apiFetch("/deployments/backends"),
  });
}

export function useCreateDeployment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateDeploymentInput) =>
      apiFetch<Deployment>("/deployments", {
        method: "POST",
        body: JSON.stringify(data),
      }),
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
    mutationFn: (id: string) => apiFetch(`/deployments/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["deployments"] }),
  });
}
