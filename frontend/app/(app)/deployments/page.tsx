"use client";

import { useRouter } from "next/navigation";
import { useDeployments, useDeploymentAction, useDeleteDeployment } from "@/hooks/useDeployments";
import { GlassCard, StatusBadge, LoadingPage } from "@/components/ui/cards";
import { Play, Square, RotateCw, Trash2, Terminal, Cpu, Plus } from "lucide-react";

export default function DeploymentsPage() {
  const router = useRouter();
  const { data: deployments, isLoading } = useDeployments();
  const deploymentAction = useDeploymentAction();
  const deleteDeployment = useDeleteDeployment();

  if (isLoading) return <LoadingPage />;

  const list = deployments || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Deployments</h1>
          <p className="text-muted-foreground">Manage local model deployments</p>
        </div>
        <button
          onClick={() => router.push("/deployments/new")}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" /> New Deployment
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {list.map((d) => (
          <GlassCard key={d.id}>
            <div className="flex items-start justify-between">
              <div className="min-w-0">
                <h3 className="font-semibold truncate">{d.model_ref}</h3>
                <p className="text-sm text-muted-foreground capitalize">{d.backend_type}</p>
              </div>
              <StatusBadge status={d.status} />
            </div>

            {d.download_progress_pct != null && d.status === "downloading" && (
              <div className="mt-3 h-1.5 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${d.download_progress_pct}%` }}
                />
              </div>
            )}

            <div className="mt-4 grid grid-cols-3 gap-4">
              <div className="text-center p-3 rounded-lg bg-background/50">
                <Cpu className="w-4 h-4 mx-auto mb-1 text-muted-foreground" />
                <p className="text-lg font-bold">{d.gpu_index ?? "—"}</p>
                <p className="text-xs text-muted-foreground">GPU</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-background/50">
                <Terminal className="w-4 h-4 mx-auto mb-1 text-muted-foreground" />
                <p className="text-lg font-bold text-xs truncate">{d.port ?? "—"}</p>
                <p className="text-xs text-muted-foreground">Port</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-background/50">
                <Play className="w-4 h-4 mx-auto mb-1 text-muted-foreground" />
                <p className="text-lg font-bold text-xs truncate">{String(d.config?.quantization ?? "—")}</p>
                <p className="text-xs text-muted-foreground">Quant</p>
              </div>
            </div>

            {d.error_message && (
              <p className="mt-3 text-xs text-red-400 font-mono truncate">{d.error_message}</p>
            )}

            <div className="mt-4 flex gap-2">
              {d.status === "stopped" || d.status === "error" ? (
                <button
                  onClick={() => deploymentAction.mutate({ id: d.id, action: "start" })}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-green-500/10 text-green-500 text-sm hover:bg-green-500/20 transition-colors"
                >
                  <Play className="w-3 h-3" /> Start
                </button>
              ) : d.status === "running" ? (
                <>
                  <button
                    onClick={() => deploymentAction.mutate({ id: d.id, action: "stop" })}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-yellow-500/10 text-yellow-500 text-sm hover:bg-yellow-500/20 transition-colors"
                  >
                    <Square className="w-3 h-3" /> Stop
                  </button>
                  <button
                    onClick={() => deploymentAction.mutate({ id: d.id, action: "restart" })}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors"
                  >
                    <RotateCw className="w-3 h-3" /> Restart
                  </button>
                </>
              ) : (
                <button
                  disabled
                  className="flex-1 px-3 py-2 rounded-lg border border-border/50 text-sm text-muted-foreground"
                >
                  {d.status}…
                </button>
              )}
              <button
                onClick={() => deleteDeployment.mutate(d.id)}
                className="px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-destructive/10 hover:text-destructive transition-colors"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          </GlassCard>
        ))}
        {list.length === 0 && (
          <GlassCard className="col-span-full text-center py-12">
            <p className="text-muted-foreground">No deployments running.</p>
            <button
              onClick={() => router.push("/deployments/new")}
              className="mt-4 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Deploy Your First Model
            </button>
          </GlassCard>
        )}
      </div>
    </div>
  );
}
