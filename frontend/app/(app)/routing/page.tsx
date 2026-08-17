"use client";

import { toast } from "sonner";
import {
  usePolicies,
  useActivatePolicy,
  useDeletePolicy,
} from "@/hooks/usePolicies";
import { GlassCard, StatusBadge, LoadingPage } from "@/components/ui/cards";
import { Plus, Zap, Trash2 } from "lucide-react";

/** `RoutingStrategy` values are snake_case; render them as words. */
function strategyLabel(strategy: string): string {
  return strategy.replace(/_/g, " ");
}

export default function RoutingPage() {
  const { data: policies, isLoading, isError, error } = usePolicies();
  const activatePolicy = useActivatePolicy();
  const deletePolicy = useDeletePolicy();

  if (isLoading) return <LoadingPage />;

  const list = policies ?? [];

  async function handleActivate(id: string) {
    try {
      const result = await activatePolicy.mutateAsync(id);
      // The backend reports "deferred" when the gateway did not hot-reload.
      // Surfacing that honestly beats a blanket success toast.
      if (result.gateway_config_status === "applied") {
        toast.success("Policy activated");
      } else {
        toast.warning("Policy saved, gateway reload deferred", {
          description:
            result.gateway_detail ?? "It takes effect on the gateway's next restart.",
        });
      }
    } catch (err) {
      toast.error("Could not activate policy", {
        description: err instanceof Error ? err.message : "Unknown error.",
      });
    }
  }

  async function handleDelete(id: string) {
    try {
      await deletePolicy.mutateAsync(id);
      toast.success("Policy deleted");
    } catch (err) {
      toast.error("Could not delete policy", {
        description: err instanceof Error ? err.message : "Unknown error.",
      });
    }
  }

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Routing Policies</h1>
          <p className="text-muted-foreground">
            Configure how requests are routed to models
          </p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
          <Plus className="w-4 h-4" /> New Policy
        </button>
      </div>

      {isError && (
        <GlassCard title="Could not load policies">
          <p className="text-sm text-red-400">{(error as Error).message}</p>
        </GlassCard>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {list.map((policy) => (
          <GlassCard key={policy.id} className="relative">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    policy.is_active ? "bg-green-500/10" : "bg-accent"
                  }`}
                >
                  <Zap
                    className={`w-5 h-5 ${
                      policy.is_active ? "text-green-500" : "text-muted-foreground"
                    }`}
                  />
                </div>
                <div>
                  <h3 className="font-semibold">{policy.name}</h3>
                  <p className="text-sm text-muted-foreground capitalize">
                    {strategyLabel(policy.strategy)}
                  </p>
                </div>
              </div>
              {policy.is_active ? (
                <StatusBadge status="active" />
              ) : (
                <button
                  onClick={() => handleActivate(policy.id)}
                  disabled={activatePolicy.isPending}
                  className="px-3 py-1 rounded-lg border border-border/50 text-xs hover:bg-accent transition-colors disabled:opacity-50"
                >
                  Activate
                </button>
              )}
            </div>
            <div className="mt-4 space-y-2">
              <div className="text-sm">
                <span className="text-muted-foreground">Models: </span>
                <span className="font-medium">
                  {policy.model_allowlist.length === 0
                    ? "all allowed"
                    : `${policy.model_allowlist.length} allowed`}
                </span>
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <button
                onClick={() => handleDelete(policy.id)}
                disabled={deletePolicy.isPending}
                className="px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-destructive/10 hover:text-destructive transition-colors disabled:opacity-50"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          </GlassCard>
        ))}
        {!isError && list.length === 0 && (
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
