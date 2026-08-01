"use client";

import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Plus, Upload, Play, BarChart3 } from "lucide-react";

export default function BenchmarksPage() {
  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Benchmarks</h1>
          <p className="text-muted-foreground">Run evaluation benchmarks across models</p>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
            <Upload className="w-4 h-4" />
            Upload Dataset
          </button>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
            <Play className="w-4 h-4" />
            New Benchmark
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard title="Datasets">
          <div className="space-y-2">
            {[
              { name: "math_problems.csv", rows: 500, format: "CSV", uploaded: "2 days ago" },
              { name: "qa_eval.json", rows: 200, format: "JSON", uploaded: "1 week ago" },
              { name: "code_review_prompts.csv", rows: 150, format: "CSV", uploaded: "3 days ago" },
            ].map((ds, i) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-border/50">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-xs font-bold text-blue-500">
                    {ds.format}
                  </div>
                  <div>
                    <p className="text-sm font-medium">{ds.name}</p>
                    <p className="text-xs text-muted-foreground">{ds.rows} rows · Uploaded {ds.uploaded}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard title="Recent Runs">
          <div className="space-y-2">
            {[
              { dataset: "math_problems.csv", models: 3, status: "complete", progress: 100 },
              { dataset: "qa_eval.json", models: 2, status: "running", progress: 67 },
              { dataset: "code_review_prompts.csv", models: 4, status: "pending", progress: 0 },
            ].map((run, i) => (
              <div key={i} className="p-3 rounded-lg border border-border/50">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium">{run.dataset}</p>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    run.status === "complete"
                      ? "bg-green-500/10 text-green-500"
                      : run.status === "running"
                      ? "bg-yellow-500/10 text-yellow-500"
                      : "bg-muted text-muted-foreground"
                  }`}>
                    {run.status}
                  </span>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>{run.models} models</span>
                  <span>{run.progress}% complete</span>
                </div>
                {run.status === "running" && (
                  <div className="mt-2 h-1.5 bg-background rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all duration-500"
                      style={{ width: `${run.progress}%` }}
                    />
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
