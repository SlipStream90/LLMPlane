"use client";

import { useProviders, useDeleteProvider } from "@/hooks/useProviders";
import { GlassCard, StatusBadge, LoadingPage } from "@/components/ui/cards";
import { ProviderWizard } from "@/components/provider-wizard";
import { Plus, RefreshCw, Trash2, ExternalLink } from "lucide-react";
import { useState } from "react";

export default function ProvidersPage() {
  const { data: providers, isLoading } = useProviders();
  const deleteProvider = useDeleteProvider();
  const [showForm, setShowForm] = useState(false);

  if (isLoading) return <LoadingPage />;

  const list = providers || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Providers</h1>
          <p className="text-muted-foreground">Manage your LLM provider connections</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Provider
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {list.map((p) => (
          <GlassCard key={p.id} className="relative group">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-accent flex items-center justify-center">
                  <span className="text-lg font-bold capitalize">{p.provider_type[0]}</span>
                </div>
                <div>
                  <h3 className="font-semibold">{p.display_name}</h3>
                  <p className="text-sm text-muted-foreground capitalize">{p.provider_type}</p>
                </div>
              </div>
              <StatusBadge status={p.health_status} />
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Endpoint</span>
                <span className="font-medium truncate max-w-[60%]" title={p.base_url ?? undefined}>
                  {p.base_url || "default"}
                </span>
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
                <RefreshCw className="w-3 h-3" /> Health Check
              </button>
              <button className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
                <ExternalLink className="w-3 h-3" /> Models
              </button>
              <button
                onClick={() => deleteProvider.mutate(p.id)}
                className="px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-destructive/10 hover:text-destructive transition-colors"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          </GlassCard>
        ))}
        {list.length === 0 && (
          <GlassCard className="col-span-full text-center py-12">
            <p className="text-muted-foreground">No providers configured yet.</p>
            <button onClick={() => setShowForm(true)} className="mt-4 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
              Add Your First Provider
            </button>
          </GlassCard>
        )}
      </div>

      <ProviderWizard open={showForm} onClose={() => setShowForm(false)} />
    </div>
  );
}
