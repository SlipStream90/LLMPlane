"use client";

import { useProviders, useDeleteProvider } from "@/hooks/useProviders";
import {
  Panel,
  PageHeader,
  StatusBadge,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { ProviderWizard } from "@/components/provider-wizard";
import { Plus, Trash2, Plug } from "lucide-react";
import { useState } from "react";

export default function ProvidersPage() {
  const { data: providers, isLoading, isError, error, refetch } = useProviders();
  const deleteProvider = useDeleteProvider();
  const [showForm, setShowForm] = useState(false);

  if (isLoading) return <LoadingPage />;

  const list = providers || [];

  return (
    <div className="page-container">
      <PageHeader
        title="Providers"
        description="Manage your LLM provider connections."
        actions={
          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary-hover transition-colors"
          >
            <Plus className="w-4 h-4" /> Add provider
          </button>
        }
      />

      {isError && (
        <ErrorState title="Could not load providers" error={error} onRetry={refetch} />
      )}

      {!isError && list.length === 0 && (
        <EmptyState
          icon={<Plug className="w-5 h-5" />}
          title="No providers configured"
          description="Connect OpenAI, Anthropic or any OpenAI-compatible endpoint to start routing requests."
          action={
            <button
              onClick={() => setShowForm(true)}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary-hover transition-colors"
            >
              <Plus className="w-4 h-4" /> Add your first provider
            </button>
          }
        />
      )}

      {!isError && list.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {list.map((p) => (
            <Panel key={p.id} className="surface-interactive">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-md bg-surface-2 flex items-center justify-center shrink-0">
                    <span className="text-lg font-semibold uppercase">
                      {p.provider_type[0]}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <h3 className="section-header truncate">{p.display_name}</h3>
                    <p className="text-sm text-muted-foreground capitalize truncate">
                      {p.provider_type}
                    </p>
                  </div>
                </div>
                <StatusBadge status={p.health_status} />
              </div>

              <dl className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Endpoint</dt>
                  <dd
                    className="font-medium font-mono text-xs truncate max-w-[60%]"
                    title={p.base_url ?? undefined}
                  >
                    {p.base_url || "default"}
                  </dd>
                </div>
                {p.last_latency_ms != null && (
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Last latency</dt>
                    <dd className="font-medium tabular">{p.last_latency_ms} ms</dd>
                  </div>
                )}
              </dl>

              <div className="mt-4 pt-4 border-t border-border flex justify-end">
                <button
                  onClick={() => deleteProvider.mutate(p.id)}
                  disabled={deleteProvider.isPending}
                  title="Remove provider"
                  aria-label="Remove provider"
                  className="p-2 rounded-md border border-border text-muted-foreground hover:text-danger hover:border-danger/30 hover:bg-danger-subtle transition-colors disabled:opacity-50 disabled:pointer-events-none"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </Panel>
          ))}
        </div>
      )}

      <ProviderWizard open={showForm} onClose={() => setShowForm(false)} />
    </div>
  );
}
