"use client";

import { useRoutingPolicies } from "@/hooks/use-api";
import { GlassCard, StatusBadge, LoadingPage } from "@/components/ui/cards";
import { Plus, Zap, ArrowRight, Edit, Trash2 } from "lucide-react";

export default function RoutingPage() {
  const { data: policies, isLoading } = useRoutingPolicies();

  if (isLoading) return <LoadingPage />;

  const list = policies?.data || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Routing Policies</h1>
          <p className="text-muted-foreground">Configure how requests are routed to models</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
          <Plus className="w-4 h-4" />
          New Policy
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {list.map((policy: any) => (
          <GlassCard key={policy.id} className="relative">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                  policy.is_active ? "bg-green-500/10" : "bg-accent"
                }`}>
                  <Zap className={`w-5 h-5 ${policy.is_active ? "text-green-500" : "text-muted-foreground"}`} />
                </div>
                <div>
                  <h3 className="font-semibold">{policy.name}</h3>
                  <p className="text-sm text-muted-foreground capitalize">
                    {policy.strategy.replace("_", " ")}
                  </p>
                </div>
              </div>
              {policy.is_active ? (
                <StatusBadge status="active" />
              ) : (
                <button className="px-3 py-1 rounded-lg border border-border/50 text-xs hover:bg-accent transition-colors">
                  Activate
                </button>
              )}
            </div>

            <div className="mt-4 space-y-2">
              <div className="text-sm">
                <span className="text-muted-foreground">Models: </span>
                <span className="font-medium">{(policy.model_allowlist || []).length} allowed</span>
              </div>
              {policy.config && Object.keys(policy.config).length > 0 && (
                <div className="p-2 rounded bg-background/50 text-xs font-mono">
                  {JSON.stringify(policy.config, null, 2)}
                </div>
              )}
            </div>

            <div className="mt-4 flex gap-2">
              <button className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
                <Edit className="w-3 h-3" />
                Edit
              </button>
              <button className="px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-destructive/10 hover:text-destructive transition-colors">
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          </GlassCard>
        ))}

        {list.length === 0 && (
          <GlassCard className="col-span-full text-center py-12">
            <p className="text-muted-foreground">No routing policies configured.</p>
            <button className="mt-4 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
              Create Your First Policy
            </button>
          </GlassCard>
        )}
      </div>
    </div>
  );
}
