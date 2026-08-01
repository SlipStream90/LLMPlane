"use client";

import { useDeployments } from "@/hooks/use-api";
import { GlassCard, StatusBadge, LoadingPage } from "@/components/ui/cards";
import { Play, Square, RotateCw, Trash2, Terminal, Cpu, HardDrive } from "lucide-react";

export default function DeploymentsPage() {
  const { data: deployments, isLoading } = useDeployments();

  if (isLoading) return <LoadingPage />;

  const list = deployments?.data || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Deployments</h1>
          <p className="text-muted-foreground">Manage local model deployments</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
          <Play className="w-4 h-4" />
          New Deployment
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {list.map((d: any) => (
          <GlassCard key={d.id}>
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold">{d.model_ref}</h3>
                <p className="text-sm text-muted-foreground capitalize">{d.backend_type}</p>
              </div>
              <StatusBadge status={d.status} />
            </div>

            <div className="mt-4 grid grid-cols-3 gap-4">
              <div className="text-center p-3 rounded-lg bg-background/50">
                <Cpu className="w-4 h-4 mx-auto mb-1 text-muted-foreground" />
                <p className="text-lg font-bold">{d.gpu_util_pct || 0}%</p>
                <p className="text-xs text-muted-foreground">GPU</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-background/50">
                <HardDrive className="w-4 h-4 mx-auto mb-1 text-muted-foreground" />
                <p className="text-lg font-bold">{d.vram_used_mb || 0}MB</p>
                <p className="text-xs text-muted-foreground">VRAM</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-background/50">
                <Terminal className="w-4 h-4 mx-auto mb-1 text-muted-foreground" />
                <p className="text-lg font-bold">{d.port || "—"}</p>
                <p className="text-xs text-muted-foreground">Port</p>
              </div>
            </div>

            {d.download_progress_pct !== null && d.status === "downloading" && (
              <div className="mt-4">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-muted-foreground">Downloading...</span>
                  <span>{d.download_progress_pct}%</span>
                </div>
                <div className="h-2 bg-background rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-500"
                    style={{ width: `${d.download_progress_pct}%` }}
                  />
                </div>
              </div>
            )}

            <div className="mt-4 flex gap-2">
              {d.status === "stopped" || d.status === "error" ? (
                <button className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-green-500/10 text-green-500 text-sm hover:bg-green-500/20 transition-colors">
                  <Play className="w-3 h-3" />
                  Start
                </button>
              ) : d.status === "running" ? (
                <>
                  <button className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-yellow-500/10 text-yellow-500 text-sm hover:bg-yellow-500/20 transition-colors">
                    <Square className="w-3 h-3" />
                    Stop
                  </button>
                  <button className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
                    <RotateCw className="w-3 h-3" />
                    Restart
                  </button>
                </>
              ) : null}
              <button className="px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-destructive/10 hover:text-destructive transition-colors">
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          </GlassCard>
        ))}

        {list.length === 0 && (
          <GlassCard className="col-span-full text-center py-12">
            <p className="text-muted-foreground">No deployments running.</p>
            <button className="mt-4 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
              Deploy Your First Model
            </button>
          </GlassCard>
        )}
      </div>
    </div>
  );
}
