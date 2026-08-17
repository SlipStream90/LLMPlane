import { useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";
import { useWebSocket } from "@/components/shared/WebSocketProvider";

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

export interface GpuTelemetrySample {
  sampled_at: string;
  gpu_index: number;
  gpu_util_pct: number;
  vram_used_mb: number;
  vram_total_mb: number;
  cpu_util_pct: number | null;
  ram_used_mb: number | null;
}

export type DeploymentAction = "start" | "stop" | "restart";

export function useDeployments() {
  return useQuery<Deployment[]>({
    queryKey: ["deployments"],
    queryFn: () => apiFetch("/deployments"),
  });
}

/** Single deployment, derived from the list — the API exposes no `GET /deployments/{id}`. */
export function useDeployment(id: string) {
  const { data, ...rest } = useDeployments();
  return { ...rest, data: data?.find((d) => d.id === id) };
}

export function useDeploymentBackends() {
  return useQuery<{ gpu_available: boolean; backends: DeploymentBackendOption[] }>({
    queryKey: ["deployments", "backends"],
    queryFn: () => apiFetch("/deployments/backends"),
  });
}

export function useDeploymentTelemetry(id: string, minutes = 30) {
  return useQuery<GpuTelemetrySample[]>({
    queryKey: ["deployments", id, "telemetry", minutes],
    queryFn: () => apiFetch(`/deployments/${id}/telemetry?minutes=${minutes}`),
    enabled: !!id,
    refetchInterval: 15_000,
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
    onSuccess: (d) => {
      toast.success("Deployment queued", {
        description: `${d.model_ref} is being pulled and started.`,
      });
      qc.invalidateQueries({ queryKey: ["deployments"] });
    },
    onError: (e: Error) => toast.error("Could not create deployment", { description: e.message }),
  });
}

const ACTION_LABEL: Record<DeploymentAction, string> = {
  start: "Start requested",
  stop: "Stop requested",
  restart: "Restart requested",
};

export function useDeploymentAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: DeploymentAction }) =>
      apiFetch<Deployment>(`/deployments/${id}/${action}`, { method: "POST" }),
    // Deliberately NOT writing the response into the cache. stop/start/restart
    // validate, enqueue a Celery task and return the row *unchanged* — the
    // status transition is the worker's to make. Seeding the cache with that
    // body would visibly revert the row to its pre-action status.
    onSuccess: (_data, { action }) => {
      toast.success(ACTION_LABEL[action], {
        description: "Waiting for the worker to apply it.",
      });
      qc.invalidateQueries({ queryKey: ["deployments"] });
    },
    onError: (e: Error, { action }) =>
      toast.error(`Could not ${action} deployment`, { description: e.message }),
  });
}

export function useDeleteDeployment() {
  const qc = useQueryClient();
  return useMutation({
    // 202 + `{status, deployment_id}` — unlike every other DELETE in this API,
    // which returns 204. The row survives until the worker removes the
    // container, so optimistic removal from the list would be wrong.
    mutationFn: ({ id, removeVolume = false }: { id: string; removeVolume?: boolean }) =>
      apiFetch<{ status: string; deployment_id: string }>(
        `/deployments/${id}?remove_volume=${removeVolume}`,
        { method: "DELETE" }
      ),
    onSuccess: () => {
      toast.success("Deletion queued", {
        description: "The row disappears once the container is torn down.",
      });
      qc.invalidateQueries({ queryKey: ["deployments"] });
    },
    onError: (e: Error) => toast.error("Could not delete deployment", { description: e.message }),
  });
}

/**
 * Keeps the deployment list fresh from the `deployments` WebSocket topic.
 *
 * Events: `deployment_created`, `deployment_status`, `deployment_deleted`
 * (published by the backend on create and by the worker on every transition).
 * Without this the list only updated on refetch, so a container that finished
 * downloading looked stuck until the user reloaded.
 */
export function useDeploymentLiveSync() {
  const { subscribe } = useWebSocket();
  const qc = useQueryClient();

  useEffect(
    () =>
      subscribe("deployments", () => {
        qc.invalidateQueries({ queryKey: ["deployments"] });
      }),
    [subscribe, qc]
  );
}
