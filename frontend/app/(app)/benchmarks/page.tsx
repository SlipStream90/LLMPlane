"use client";

import { useBenchmarks } from "@/hooks/useBenchmarks";
import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Upload, Play } from "lucide-react";

export default function BenchmarksPage() {
  const { data: benchmarks, isLoading } = useBenchmarks();

  if (isLoading) return <LoadingPage />;

  const list = benchmarks || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Benchmarks</h1>
          <p className="text-muted-foreground">Run evaluation benchmarks across models</p>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
            <Upload className="w-4 h-4" /> Upload Dataset
          </button>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
            <Play className="w-4 h-4" /> New Benchmark
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard title="Datasets">
          <div className="space-y-2">
            {list.map((ds) => (
              <div key={ds.id} className="flex items-center justify-between p-3 rounded-lg border border-border/50">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-xs font-bold text-blue-500">DS</div>
                  <div>
                    <p className="text-sm font-medium">{ds.dataset_name}</p>
                    <p className="text-xs text-muted-foreground">{ds.total_items} items</p>
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded-full text-xs ${ds.status === "completed" ? "bg-green-500/10 text-green-500" : ds.status === "running" ? "bg-yellow-500/10 text-yellow-500" : "bg-muted text-muted-foreground"}`}>
                  {ds.status}
                </span>
              </div>
            ))}
            {list.length === 0 && <div className="text-center py-8 text-muted-foreground">No datasets uploaded.</div>}
          </div>
        </GlassCard>

        <GlassCard title="Recent Runs">
          <div className="space-y-2">
            {list.filter((b) => b.status !== "pending").map((run) => (
              <div key={run.id} className="p-3 rounded-lg border border-border/50">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium">{run.name}</p>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${run.status === "completed" ? "bg-green-500/10 text-green-500" : run.status === "running" ? "bg-yellow-500/10 text-yellow-500" : "bg-muted text-muted-foreground"}`}>
                    {run.status}
                  </span>
                </div>
                {run.status === "running" && (
                  <div className="mt-2 h-1.5 bg-background rounded-full overflow-hidden">
                    <div className="h-full bg-primary transition-all duration-500" style={{ width: `${run.progress}%` }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
