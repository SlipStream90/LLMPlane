"use client";

import { toast } from "sonner";
import {
  usePolicies,
  useActivatePolicy,
  useDeletePolicy,
} from "@/hooks/usePolicies";
import {
  Panel,
  PageHeader,
  StatusBadge,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { Plus, Zap, Trash2 } from "lucide-react";
import { TONE_CLASSES } from "@/lib/status";
import { cn } from "@/lib/utils";

/** `RoutingStrategy` values are snake_case; render them as words. */
function strategyLabel(strategy: string): string {
  return strategy.replace(/_/g, " ");
}

export default function RoutingPage() {
  const { data: policies, isLoading, isError, error, refetch } = usePolicies();
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
      <PageHeader
        title="Routing Policies"
        description="Configure how requests are routed to models."
        actions={
          <button
            disabled
            title="Authoring policies from the UI is not implemented yet — create them via the API."
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 disabled:pointer-events-none"
          >
            <Plus className="w-4 h-4" /> New policy
          </button>
        }
      />

      {isError && (
        <ErrorState title="Could not load policies" error={error} onRetry={refetch} />
      )}

      {!isError && list.length === 0 && (
        <EmptyState
          icon={<Zap className="w-5 h-5" />}
          title="No routing policies configured"
          description="A policy decides which model serves each request — by cost, latency, or an explicit allowlist."
        />
      )}

      {!isError && list.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {list.map((policy) => (
            <Panel key={policy.id} className="surface-interactive">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className={cn(
                      "w-10 h-10 rounded-md flex items-center justify-center shrink-0",
                      policy.is_active ? TONE_CLASSES.success.bg : "bg-surface-2"
                    )}
                  >
                    <Zap
                      className={cn(
                        "w-5 h-5",
                        policy.is_active
                          ? TONE_CLASSES.success.text
                          : "text-muted-foreground"
                      )}
                    />
                  </div>
                  <div className="min-w-0">
                    <h3 className="section-header truncate">{policy.name}</h3>
                    <p className="text-sm text-muted-foreground capitalize truncate">
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
                    className="px-3 py-1 rounded-md border border-border text-xs font-medium hover:bg-surface-2 transition-colors disabled:opacity-50 disabled:pointer-events-none shrink-0"
                  >
                    Activate
                  </button>
                )}
              </div>

              <div className="mt-4 text-sm">
                <span className="text-muted-foreground">Models: </span>
                <span className="font-medium tabular">
                  {policy.model_allowlist.length === 0
                    ? "all allowed"
                    : `${policy.model_allowlist.length} allowed`}
                </span>
              </div>

              <div className="mt-4 pt-4 border-t border-border flex justify-end">
                <button
                  onClick={() => handleDelete(policy.id)}
                  disabled={deletePolicy.isPending}
                  title="Delete policy"
                  aria-label="Delete policy"
                  className="p-2 rounded-md border border-border text-muted-foreground hover:text-danger hover:border-danger/30 hover:bg-danger-subtle transition-colors disabled:opacity-50 disabled:pointer-events-none"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </Panel>
          ))}
        </div>
      )}
    </div>
  );
}
