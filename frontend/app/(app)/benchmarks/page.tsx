"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import {
  useBenchmarks,
  useBenchmarkDatasets,
  useUploadBenchmarkDataset,
  type RunStatus,
} from "@/hooks/useBenchmarks";
import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Upload, Play, Loader2 } from "lucide-react";

const STATUS_STYLE: Record<RunStatus, string> = {
  complete: "bg-green-500/10 text-green-500",
  running: "bg-yellow-500/10 text-yellow-500",
  failed: "bg-red-500/10 text-red-500",
  pending: "bg-muted text-muted-foreground",
};

const ACCEPT = ".csv,.json,text/csv,application/json";

export default function BenchmarksPage() {
  const datasets = useBenchmarkDatasets();
  const runs = useBenchmarks();
  const upload = useUploadBenchmarkDataset();
  const fileInput = useRef<HTMLInputElement>(null);
  const [pendingName, setPendingName] = useState<string | null>(null);

  // Only the datasets panel gates on its own load — a slow runs query no
  // longer blanks the whole page.
  const datasetList = datasets.data ?? [];
  const runList = runs.data ?? [];

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file after a failure
    if (!file) return;

    const name = file.name.replace(/\.(csv|json)$/i, "").trim() || file.name;
    setPendingName(name);
    try {
      const created = await upload.mutateAsync({ file, name });
      toast.success(`Uploaded "${created.name}"`, {
        description: `${created.row_count.toLocaleString()} rows · ${created.columns.length} columns`,
      });
    } catch (err) {
      toast.error("Upload failed", {
        description: err instanceof Error ? err.message : "Unknown error.",
      });
    } finally {
      setPendingName(null);
    }
  }

  if (datasets.isLoading && runs.isLoading) return <LoadingPage />;

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Benchmarks</h1>
          <p className="text-muted-foreground">Run evaluation benchmarks across models</p>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={handleFile}
          />
          <button
            onClick={() => fileInput.current?.click()}
            disabled={upload.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {upload.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Upload className="w-4 h-4" />
            )}
            {upload.isPending ? `Uploading ${pendingName}…` : "Upload Dataset"}
          </button>
          <button
            disabled={datasetList.length === 0}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={
              datasetList.length === 0 ? "Upload a dataset first" : "Start a benchmark run"
            }
          >
            <Play className="w-4 h-4" /> New Benchmark
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard title="Datasets">
          <div className="space-y-2">
            {datasets.isError && (
              <div className="text-center py-8 text-red-400 text-sm">
                Could not load datasets: {(datasets.error as Error).message}
              </div>
            )}
            {datasetList.map((ds) => (
              <div
                key={ds.id}
                className="flex items-center justify-between p-3 rounded-lg border border-border/50"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center text-[10px] font-bold text-blue-500 uppercase">
                    {ds.source_format}
                  </div>
                  <div>
                    <p className="text-sm font-medium">{ds.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {ds.row_count.toLocaleString()} rows · {ds.columns.length} columns
                    </p>
                  </div>
                </div>
              </div>
            ))}
            {!datasets.isLoading && !datasets.isError && datasetList.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                No datasets uploaded.
              </div>
            )}
          </div>
        </GlassCard>

        <GlassCard title="Recent Runs">
          <div className="space-y-2">
            {runs.isError && (
              <div className="text-center py-8 text-red-400 text-sm">
                Could not load runs: {(runs.error as Error).message}
              </div>
            )}
            {runList.map((run) => {
              const pct =
                run.total_items > 0
                  ? Math.round((run.completed_items / run.total_items) * 100)
                  : 0;
              const dataset = datasetList.find((d) => d.id === run.dataset_id);
              return (
                <div key={run.id} className="p-3 rounded-lg border border-border/50">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium">
                      {dataset?.name ?? `Run ${run.id.slice(0, 8)}`}
                    </p>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs ${STATUS_STYLE[run.status]}`}
                    >
                      {run.status}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {run.completed_items.toLocaleString()} /{" "}
                    {run.total_items.toLocaleString()} items
                  </p>
                  {run.status === "running" && (
                    <div className="mt-2 h-1.5 bg-background rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  )}
                  {run.error_message && (
                    <p className="mt-2 text-xs text-red-400">{run.error_message}</p>
                  )}
                </div>
              );
            })}
            {!runs.isLoading && !runs.isError && runList.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">No runs yet.</div>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
