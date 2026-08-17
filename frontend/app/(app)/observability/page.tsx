"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTraces } from "@/hooks/useTraces";
import { buildWaterfall } from "@/lib/trace-spans";
import {
  Panel,
  PageHeader,
  StatusBadge,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { Search, Filter, ExternalLink, Clock, RotateCw, Route } from "lucide-react";
import { toneFor, TONE_CLASSES } from "@/lib/status";
import { cn, formatLatency, formatCurrency, formatTokens } from "@/lib/utils";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "success", label: "Success" },
  { value: "error", label: "Error" },
  { value: "timeout", label: "Timeout" },
];

export default function ObservabilityPage() {
  const router = useRouter();
  const [modelQuery, setModelQuery] = useState("");
  const [status, setStatus] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: traces, isLoading, isError, error, refetch } = useTraces({
    model_id: modelQuery || undefined,
    status: status || undefined,
    limit: 100,
  });

  if (isLoading) return <LoadingPage />;

  const list = traces || [];
  const selected = list.find((t) => t.id === selectedId) || list[0] || null;
  const spans = selected ? buildWaterfall(selected) : [];
  const maxTotal = selected?.latency_ms || 1;

  return (
    <div className="page-container">
      <PageHeader
        title="Trace Explorer"
        description="Request traces and their lifecycle waterfall."
        actions={
          <a
            href="https://cloud.langfuse.com"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md border border-border text-sm font-medium hover:bg-surface-2 transition-colors"
          >
            <ExternalLink className="w-4 h-4" /> Open Langfuse
          </a>
        }
      />

      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <input
            type="text"
            value={modelQuery}
            onChange={(e) => setModelQuery(e.target.value)}
            placeholder="Filter by model id…"
            aria-label="Filter by model id"
            className="pl-9 pr-4 py-2 rounded-md bg-surface-1 border border-border text-sm w-full"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            aria-label="Filter by status"
            className="pl-9 pr-8 py-2 rounded-md bg-surface-1 border border-border text-sm appearance-none"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isError && <ErrorState title="Could not load traces" error={error} onRetry={refetch} />}

      {!isError && list.length === 0 && (
        <EmptyState
          icon={<Route className="w-5 h-5" />}
          title="No traces recorded"
          description="Send requests through the gateway and each one shows up here with its lifecycle breakdown."
        />
      )}

      {!isError && list.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-4">
          {/* List */}
          <Panel className="max-h-[70vh] overflow-y-auto">
            <div className="space-y-2">
              {list.map((trace) => (
                <button
                  key={trace.id}
                  onClick={() => setSelectedId(trace.id)}
                  aria-pressed={selected?.id === trace.id}
                  className={cn(
                    "w-full text-left flex items-center justify-between gap-3 p-3 rounded-md border transition-colors",
                    selected?.id === trace.id
                      ? "border-primary/40 bg-primary-subtle"
                      : "border-border hover:bg-surface-2"
                  )}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span
                      className={cn(
                        "w-2 h-2 rounded-full shrink-0",
                        TONE_CLASSES[toneFor(trace.status)].dot
                      )}
                    />
                    <div className="min-w-0">
                      <p className="font-mono text-xs text-muted-foreground truncate">
                        {trace.trace_id || trace.id.slice(0, 12)}
                      </p>
                      <p className="text-sm font-medium truncate">{trace.model_id}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0 tabular">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatLatency(trace.latency_ms)}
                    </span>
                    <span>{formatTokens(trace.input_tokens + trace.output_tokens)}</span>
                  </div>
                </button>
              ))}
            </div>
          </Panel>

          {/* Detail + waterfall */}
          <Panel>
            {selected ? (
              <div className="space-y-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="section-header truncate">{selected.model_id}</h3>
                      <StatusBadge status={selected.status} />
                    </div>
                    <p className="font-mono text-xs text-muted-foreground mt-1 truncate">
                      {selected.trace_id || selected.id}
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      router.push(`/playground?model=${encodeURIComponent(selected.model_id)}`)
                    }
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary-subtle text-primary text-sm font-medium hover:brightness-110 transition-all shrink-0"
                  >
                    <RotateCw className="w-3.5 h-3.5" /> Replay
                  </button>
                </div>

                {/* Waterfall */}
                <div>
                  <p className="text-xs uppercase tracking-wider text-subtle-foreground mb-2">
                    Lifecycle waterfall
                  </p>
                  <div className="space-y-1.5">
                    {spans.map((s) => (
                      <div key={s.name} className="flex items-center gap-3 text-xs">
                        <span className="w-24 shrink-0 text-muted-foreground truncate">
                          {s.name}
                        </span>
                        <div className="flex-1 h-4 bg-surface-2 rounded relative overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded",
                              s.status === "error" ? "bg-danger" : "bg-primary"
                            )}
                            style={{
                              marginLeft: `${(s.start_ms / maxTotal) * 100}%`,
                              width: `${(s.duration_ms / maxTotal) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="w-14 shrink-0 text-right font-mono tabular">
                          {formatLatency(s.duration_ms)}
                        </span>
                      </div>
                    ))}
                    <div className="flex items-center gap-3 text-xs pt-1 border-t border-border">
                      <span className="w-24 shrink-0 font-medium">Total</span>
                      <div className="flex-1" />
                      <span className="w-14 shrink-0 text-right font-mono font-medium tabular">
                        {formatLatency(maxTotal)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Metadata */}
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <Meta label="Cost" value={formatCurrency(selected.cost_usd)} />
                  <Meta
                    label="Tokens"
                    value={`${formatTokens(selected.input_tokens)} → ${formatTokens(selected.output_tokens)}`}
                  />
                  <Meta
                    label="TTFT"
                    value={selected.ttft_ms == null ? "—" : formatLatency(selected.ttft_ms)}
                  />
                  <Meta
                    label="Requested"
                    value={new Date(selected.requested_at).toLocaleString()}
                  />
                </div>

                {selected.error_message && (
                  <div className="p-3 rounded-md bg-danger-subtle border border-danger/25 text-sm text-danger font-mono break-words">
                    {selected.error_message}
                  </div>
                )}

                {selected.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {selected.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-0.5 rounded-full text-xs bg-surface-2 text-muted-foreground"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <EmptyState
                title="Select a trace"
                description="Pick a request on the left to inspect its lifecycle waterfall."
                className="border-0"
              />
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-3 rounded-md bg-surface-2">
      <p className="text-xs text-subtle-foreground">{label}</p>
      <p className="font-mono mt-1 truncate tabular">{value}</p>
    </div>
  );
}
