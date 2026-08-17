"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";
import {
  useBenchmarks,
  useBenchmarkDatasets,
  useUploadBenchmarkDataset,
} from "@/hooks/useBenchmarks";
import {
  Panel,
  PageHeader,
  StatusBadge,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { Upload, Play, Loader2, Database, FlaskConical } from "lucide-react";

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
      <PageHeader
        title="Benchmarks"
        description="Run evaluation benchmarks across models."
        actions={
          <>
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
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md border border-border text-sm font-medium hover:bg-surface-2 transition-colors disabled:opacity-60 disabled:pointer-events-none"
            >
              {upload.isPending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4" />
              )}
              {upload.isPending ? `Uploading ${pendingName}…` : "Upload dataset"}
            </button>
            <button
              disabled
              title="Starting a benchmark run is not wired up in the UI yet — trigger runs via the API."
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 disabled:pointer-events-none"
            >
              <Play className="w-4 h-4" /> New benchmark
            </button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Datasets">
          {datasets.isError ? (
            <ErrorState
              title="Could not load datasets"
              error={datasets.error}
              onRetry={datasets.refetch}
            />
          ) : datasetList.length === 0 ? (
            <EmptyState
              icon={<Database className="w-5 h-5" />}
              title="No datasets uploaded"
              description="Upload a CSV or JSON file and it will appear here, ready to benchmark against."
            />
          ) : (
            <div className="space-y-2">
              {datasetList.map((ds) => (
                <div
                  key={ds.id}
                  className="flex items-center justify-between p-3 rounded-md border border-border"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-md bg-info-subtle flex items-center justify-center text-[10px] font-bold text-info uppercase shrink-0">
                      {ds.source_format}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{ds.name}</p>
                      <p className="text-xs text-muted-foreground tabular">
                        {ds.row_count.toLocaleString()} rows · {ds.columns.length} columns
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Recent runs">
          {runs.isError ? (
            <ErrorState
              title="Could not load runs"
              error={runs.error}
              onRetry={runs.refetch}
            />
          ) : runList.length === 0 ? (
            <EmptyState
              icon={<FlaskConical className="w-5 h-5" />}
              title="No runs yet"
              description="Benchmark runs report per-item progress here as the worker processes them."
            />
          ) : (
            <div className="space-y-2">
              {runList.map((run) => {
                const pct =
                  run.total_items > 0
                    ? Math.round((run.completed_items / run.total_items) * 100)
                    : 0;
                const dataset = datasetList.find((d) => d.id === run.dataset_id);
                return (
                  <div key={run.id} className="p-3 rounded-md border border-border">
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <p className="text-sm font-medium truncate">
                        {dataset?.name ?? `Run ${run.id.slice(0, 8)}`}
                      </p>
                      <StatusBadge status={run.status} />
                    </div>
                    <p className="text-xs text-muted-foreground tabular">
                      {run.completed_items.toLocaleString()} /{" "}
                      {run.total_items.toLocaleString()} items
                    </p>
                    {run.status === "running" && (
                      <div className="mt-2 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    )}
                    {run.error_message && (
                      <p className="mt-2 text-xs text-danger font-mono break-words">
                        {run.error_message}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
