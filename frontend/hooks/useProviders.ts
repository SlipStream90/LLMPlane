import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

//: Health status as reported by `ProviderHealthService` — written by a check,
//: never computed on read. "unknown" covers a provider that has never been
//: probed yet.
export type HealthStatus = "healthy" | "degraded" | "down" | "unknown";

//: Mirrors `schemas/provider.py`'s `ProviderOut` field-for-field — this is
//: the actual JSON shape `GET /providers` returns (R6 bug fix: the previous
//: interface here — name/type/status/models/config — matched nothing the
//: backend ever sent).
export interface Provider {
  id: string;
  project_id: string;
  provider_type: string;
  display_name: string;
  base_url: string | null;
  is_active: boolean;
  health_status: HealthStatus;
  last_health_check_at: string | null;
  last_latency_ms: number | null;
  created_at: string;
  //: Masked, e.g. "********a1b2". Never the full key.
  credential_hint: string | null;
  has_credentials: boolean;
  //: Set when this provider is backed by a plugin (net-new alongside the
  //: plugin system).
  plugin_id: string | null;
}

export interface ProviderModel {
  id: string;
  provider_id: string;
  model_id: string;
  display_name: string;
  context_window: number;
  input_price_per_1m: string | null;
  output_price_per_1m: string | null;
  capabilities: string[];
  is_available: boolean;
}

//: Mirrors `schemas/provider.py`'s `ProviderCreate`.
export interface ProviderCreateInput {
  provider_type: string;
  display_name: string;
  api_key?: string;
  base_url?: string;
  extra_credentials?: Record<string, string>;
  plugin_id?: string;
}

//: Mirrors `schemas/provider.py`'s `ProviderUpdate`. Deliberately does not
//: extend `Partial<Provider>` — that would let a caller "update" fields like
//: `id`/`created_at`/`health_status` that the PATCH endpoint neither accepts
//: nor would honor.
export interface ProviderUpdateInput {
  display_name?: string;
  api_key?: string;
  base_url?: string;
  is_active?: boolean;
  extra_credentials?: Record<string, string>;
}

//: Mirrors `schemas/provider.py`'s `PluginManifestOut`.
export interface PluginManifest {
  id: string;
  display_name: string;
  auth_type: "api_key" | "none" | "bearer_token";
  default_base_url: string | null;
  requires_base_url: boolean;
  capabilities: string[];
  pricing_hint: Record<string, number> | null;
}

//: Mirrors `schemas/provider.py`'s `DiscoveredModelOut`.
export interface DiscoveredModel {
  model_id: string;
  display_name: string;
  context_window: number | null;
  capabilities: string[];
}

//: Mirrors `schemas/provider.py`'s `ModelDiscoveryOut`.
export interface ModelDiscovery {
  provider_id: string;
  models: DiscoveredModel[];
}

//: One row of `schemas/provider.py`'s `ProviderModelCreate`, as consumed by
//: `BulkModelConfirm`.
export interface ProviderModelCreateInput {
  model_id: string;
  display_name?: string;
  context_window?: number;
  input_price_per_1m?: number | null;
  output_price_per_1m?: number | null;
  capabilities?: string[];
}

export function useProviders() {
  return useQuery<Provider[]>({
    queryKey: ["providers"],
    queryFn: () => apiFetch("/providers"),
  });
}

export function useProvider(id: string) {
  return useQuery<Provider>({
    queryKey: ["providers", id],
    queryFn: () => apiFetch(`/providers/${id}`),
    enabled: !!id,
  });
}

export function useCreateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProviderCreateInput) =>
      apiFetch<Provider>("/providers", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });
}

export function useUpdateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: ProviderUpdateInput & { id: string }) =>
      apiFetch<Provider>(`/providers/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });
}

export function useDeleteProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/providers/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });
}

//: `GET /providers/plugins` — feeds the wizard's provider-type picker
//: alongside the existing 11 first-party `ProviderType` values.
export function usePluginManifests() {
  return useQuery<PluginManifest[]>({
    queryKey: ["providers", "plugins"],
    queryFn: () => apiFetch("/providers/plugins"),
    staleTime: 5 * 60_000,
  });
}

//: `POST /providers/{id}/discover-models` — read-only, does not persist.
//: The wizard's model-discovery step calls this once the provider row exists.
export function useDiscoverModels() {
  return useMutation({
    mutationFn: (providerId: string) =>
      apiFetch<ModelDiscovery>(`/providers/${providerId}/discover-models`, {
        method: "POST",
      }),
  });
}

//: `POST /providers/{id}/models/bulk-confirm` — the wizard's final step,
//: persisting the user-reviewed subset of `useDiscoverModels`' result.
export function useBulkConfirmModels() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      providerId,
      models,
    }: {
      providerId: string;
      models: ProviderModelCreateInput[];
    }) =>
      apiFetch<ProviderModel[]>(`/providers/${providerId}/models/bulk-confirm`, {
        method: "POST",
        body: JSON.stringify({ models }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["providers"] }),
  });
}
