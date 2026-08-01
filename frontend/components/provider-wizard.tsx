"use client";

import { useMemo, useState } from "react";
import { X, Loader2, Check, ChevronLeft, ChevronRight, Server, Plug } from "lucide-react";
import { GlassCard } from "@/components/ui/cards";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  usePluginManifests,
  useCreateProvider,
  useDiscoverModels,
  useBulkConfirmModels,
  type PluginManifest,
  type DiscoveredModel,
  type ProviderModelCreateInput,
} from "@/hooks/useProviders";

//: The 11 first-party `ProviderType` values (backend `models/enums.py`),
//: offered in the type picker for parity with the pre-wizard create flow.
//: Plugin-backed types come from `usePluginManifests()` instead — see
//: ARCHITECTURE.md §8 step 2.
const FIRST_PARTY_TYPES: { value: string; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Gemini" },
  { value: "groq", label: "Groq" },
  { value: "mistral", label: "Mistral" },
  { value: "cohere", label: "Cohere" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "azure_openai", label: "Azure OpenAI" },
  { value: "aws_bedrock", label: "AWS Bedrock" },
  { value: "ollama", label: "Ollama (first-party)" },
  { value: "vllm", label: "vLLM (first-party)" },
];

//: First-party types reached over a caller-supplied base_url instead of an
//: API key — mirrors `schemas/provider.py`'s `_LOCAL_TYPES`.
const LOCAL_FIRST_PARTY_TYPES = new Set(["ollama", "vllm"]);

type TypeSelection =
  | { kind: "first_party"; providerType: string }
  | { kind: "plugin"; manifest: PluginManifest };

interface DiscoveredRow extends DiscoveredModel {
  selected: boolean;
}

const STEP_LABELS = ["Name", "Provider Type", "Endpoint & Auth", "Discover Models", "Confirm"];

export function ProviderWizard({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [step, setStep] = useState(1);
  const [displayName, setDisplayName] = useState("");
  const [selection, setSelection] = useState<TypeSelection | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [providerId, setProviderId] = useState<string | null>(null);
  const [rows, setRows] = useState<DiscoveredRow[]>([]);
  const [discoverError, setDiscoverError] = useState<string | null>(null);

  const { data: manifests, isLoading: manifestsLoading } = usePluginManifests();
  const createProvider = useCreateProvider();
  const discoverModels = useDiscoverModels();
  const bulkConfirm = useBulkConfirmModels();

  const authType = selection?.kind === "plugin" ? selection.manifest.auth_type : "api_key";
  const requiresBaseUrl =
    selection?.kind === "plugin"
      ? selection.manifest.requires_base_url
      : selection?.kind === "first_party"
        ? LOCAL_FIRST_PARTY_TYPES.has(selection.providerType)
        : false;
  const requiresApiKey =
    selection?.kind === "plugin"
      ? selection.manifest.auth_type !== "none"
      : selection?.kind === "first_party"
        ? !LOCAL_FIRST_PARTY_TYPES.has(selection.providerType)
        : false;
  const isPluginBacked = selection?.kind === "plugin";

  function reset() {
    setStep(1);
    setDisplayName("");
    setSelection(null);
    setApiKey("");
    setBaseUrl("");
    setCreateError(null);
    setProviderId(null);
    setRows([]);
    setDiscoverError(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  function selectType(next: TypeSelection) {
    setSelection(next);
    if (next.kind === "plugin" && next.manifest.default_base_url) {
      setBaseUrl(next.manifest.default_base_url);
    } else {
      setBaseUrl("");
    }
  }

  async function handleCreateProvider() {
    if (!selection) return;
    setCreateError(null);
    try {
      const provider = await createProvider.mutateAsync({
        display_name: displayName.trim(),
        provider_type: selection.kind === "plugin" ? "custom" : selection.providerType,
        plugin_id: selection.kind === "plugin" ? selection.manifest.id : undefined,
        api_key: requiresApiKey && apiKey ? apiKey : undefined,
        base_url: requiresBaseUrl && baseUrl ? baseUrl : undefined,
      });
      setProviderId(provider.id);
      if (isPluginBacked) {
        setStep(4);
        void runDiscovery(provider.id);
      } else {
        // No plugin to discover models from — the wizard's job ends at
        // "provider connected"; models are added the existing way.
        handleClose();
      }
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create provider.");
    }
  }

  async function runDiscovery(id: string) {
    setDiscoverError(null);
    try {
      const result = await discoverModels.mutateAsync(id);
      setRows(result.models.map((m) => ({ ...m, selected: true })));
    } catch (err) {
      setDiscoverError(
        err instanceof Error ? err.message : "Failed to discover models from this endpoint."
      );
    }
  }

  function updateRow(index: number, patch: Partial<DiscoveredRow>) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  async function handleConfirm() {
    if (!providerId) return;
    const selectedModels: ProviderModelCreateInput[] = rows
      .filter((r) => r.selected)
      .map((r) => ({
        model_id: r.model_id,
        display_name: r.display_name,
        context_window: r.context_window ?? undefined,
        capabilities: r.capabilities,
      }));
    if (selectedModels.length === 0) {
      handleClose();
      return;
    }
    await bulkConfirm.mutateAsync({ providerId, models: selectedModels });
    handleClose();
  }

  const canProceedFromStep1 = displayName.trim().length > 0;
  const canProceedFromStep2 = selection !== null;
  const canProceedFromStep3 =
    (!requiresApiKey || apiKey.trim().length > 0) &&
    (!requiresBaseUrl || baseUrl.trim().length > 0);

  const selectedCount = useMemo(() => rows.filter((r) => r.selected).length, [rows]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={handleClose} />
      <GlassCard className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold">Add Provider</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Step {step} of 5 — {STEP_LABELS[step - 1]}
            </p>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg hover:bg-accent transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-1.5 mb-6">
          {STEP_LABELS.map((label, i) => (
            <div
              key={label}
              className={cn(
                "h-1.5 flex-1 rounded-full transition-colors",
                i + 1 <= step ? "bg-primary" : "bg-muted"
              )}
            />
          ))}
        </div>

        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">Provider name</label>
              <input
                autoFocus
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. Production OpenAI"
                className="w-full px-3 py-2 rounded-lg border border-border/50 bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h3 className="text-sm font-medium mb-2">Plugins</h3>
              {manifestsLoading ? (
                <div className="grid grid-cols-2 gap-2">
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-16 w-full" />
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {(manifests || []).map((m) => (
                    <button
                      key={m.id}
                      onClick={() => selectType({ kind: "plugin", manifest: m })}
                      className={cn(
                        "flex items-start gap-2 p-3 rounded-lg border text-left transition-colors",
                        selection?.kind === "plugin" && selection.manifest.id === m.id
                          ? "border-primary bg-primary/5"
                          : "border-border/50 hover:bg-accent"
                      )}
                    >
                      <Plug className="w-4 h-4 mt-0.5 shrink-0" />
                      <div>
                        <div className="text-sm font-medium">{m.display_name}</div>
                        <div className="text-xs text-muted-foreground capitalize">
                          {m.auth_type.replace("_", " ")}
                        </div>
                      </div>
                    </button>
                  ))}
                  {!manifestsLoading && (manifests || []).length === 0 && (
                    <p className="col-span-2 text-sm text-muted-foreground">
                      No plugins registered.
                    </p>
                  )}
                </div>
              )}
            </div>

            <div>
              <h3 className="text-sm font-medium mb-2">First-party providers</h3>
              <div className="grid grid-cols-2 gap-2">
                {FIRST_PARTY_TYPES.map((t) => (
                  <button
                    key={t.value}
                    onClick={() => selectType({ kind: "first_party", providerType: t.value })}
                    className={cn(
                      "flex items-center gap-2 p-3 rounded-lg border text-left transition-colors",
                      selection?.kind === "first_party" && selection.providerType === t.value
                        ? "border-primary bg-primary/5"
                        : "border-border/50 hover:bg-accent"
                    )}
                  >
                    <Server className="w-4 h-4 shrink-0" />
                    <span className="text-sm font-medium">{t.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 3 && selection && (
          <div className="space-y-4">
            {requiresBaseUrl && (
              <div>
                <label className="text-sm font-medium mb-2 block">
                  Endpoint URL {requiresBaseUrl && <span className="text-destructive">*</span>}
                </label>
                <input
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="http://localhost:11434"
                  className="w-full px-3 py-2 rounded-lg border border-border/50 bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            )}
            {requiresApiKey ? (
              <div>
                <label className="text-sm font-medium mb-2 block">
                  {authType === "bearer_token" ? "Bearer token" : "API key"}{" "}
                  <span className="text-destructive">*</span>
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full px-3 py-2 rounded-lg border border-border/50 bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                This endpoint doesn&apos;t require a credential (auth type: none).
              </p>
            )}
            {createError && <p className="text-sm text-destructive">{createError}</p>}
          </div>
        )}

        {step === 4 && (
          <div className="space-y-3">
            {discoverModels.isPending ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : discoverError ? (
              <div className="space-y-3">
                <p className="text-sm text-destructive">{discoverError}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => providerId && runDiscovery(providerId)}
                >
                  Retry discovery
                </Button>
              </div>
            ) : rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No models found at this endpoint yet. You can discover models later from the
                provider&apos;s detail page.
              </p>
            ) : (
              <div className="space-y-1.5 max-h-80 overflow-y-auto">
                {rows.map((row, i) => (
                  <label
                    key={row.model_id}
                    className="flex items-center gap-3 p-2.5 rounded-lg border border-border/50 hover:bg-accent transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={row.selected}
                      onChange={(e) => updateRow(i, { selected: e.target.checked })}
                      className="shrink-0"
                    />
                    <input
                      value={row.display_name}
                      onChange={(e) => updateRow(i, { display_name: e.target.value })}
                      className="flex-1 min-w-0 px-2 py-1 rounded border border-transparent bg-transparent text-sm hover:border-border/50 focus:outline-none focus:border-ring"
                    />
                    <span className="text-xs text-muted-foreground shrink-0">{row.model_id}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {step === 5 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {selectedCount > 0
                ? `Register ${selectedCount} model${selectedCount === 1 ? "" : "s"} under "${displayName}".`
                : "No models selected — the provider connection will still be saved."}
            </p>
            <div className="space-y-1.5 max-h-60 overflow-y-auto">
              {rows
                .filter((r) => r.selected)
                .map((r) => (
                  <div
                    key={r.model_id}
                    className="flex items-center justify-between px-3 py-2 rounded-lg bg-accent/50 text-sm"
                  >
                    <span>{r.display_name}</span>
                    <span className="text-xs text-muted-foreground">{r.model_id}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        <div className="flex items-center justify-between mt-6 pt-4 border-t border-border/50">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1 || step === 4 || step === 5}
          >
            <ChevronLeft className="w-4 h-4 mr-1" /> Back
          </Button>

          {step === 1 && (
            <Button size="sm" onClick={() => setStep(2)} disabled={!canProceedFromStep1}>
              Next <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          )}
          {step === 2 && (
            <Button size="sm" onClick={() => setStep(3)} disabled={!canProceedFromStep2}>
              Next <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          )}
          {step === 3 && (
            <Button
              size="sm"
              onClick={handleCreateProvider}
              disabled={!canProceedFromStep3 || createProvider.isPending}
            >
              {createProvider.isPending && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Connect
            </Button>
          )}
          {step === 4 && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleClose}>
                Discover later
              </Button>
              <Button
                size="sm"
                onClick={() => setStep(5)}
                disabled={discoverModels.isPending || rows.length === 0}
              >
                Review selection <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          )}
          {step === 5 && (
            <Button size="sm" onClick={handleConfirm} disabled={bulkConfirm.isPending}>
              {bulkConfirm.isPending ? (
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
              ) : (
                <Check className="w-4 h-4 mr-1" />
              )}
              Finish
            </Button>
          )}
        </div>
      </GlassCard>
    </div>
  );
}
