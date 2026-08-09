"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTraces, type Trace } from "@/hooks/useTraces";
import { buildWaterfall } from "@/lib/trace-spans";
import { GlassCard, StatusBadge, LoadingPage } from "@/components/ui/cards";
import { Search, Filter, ExternalLink, Clock, RotateCw, ArrowRight } from "lucide-react";
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

  const { data: traces, isLoading } = useTraces({
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Trace Explorer</h1>
          <p className="text-muted-foreground">Request traces and lifecycle waterfall</p>
        </div>
        <a
          href="https://cloud.langfuse.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors"
        >
          <ExternalLink className="w-4 h-4" /> Open Langfuse
        </a>
      </div>

      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            value={modelQuery}
            onChange={(e) => setModelQuery(e.target.value)}
            placeholder="Filter by model id…"
            className="pl-9 pr-4 py-2 rounded-lg bg-background/50 border border-border/50 text-sm w-full"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="pl-9 pr-8 py-2 rounded-lg bg-background/50 border border-border/50 text-sm appearance-none"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-4">
        {/* List */}
        <GlassCard className="max-h-[70vh] overflow-y-auto">
          <div className="space-y-2">
            {list.map((trace) => (
              <button
                key={trace.id}
                onClick={() => setSelectedId(trace.id)}
                className={cn(
                  "w-full text-left flex items-center justify-between p-3 rounded-lg border transition-colors",
                  selected?.id === trace.id
                    ? "border-primary/40 bg-primary/5"
                    : "border-border/50 hover:bg-accent/30"
                )}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`w-2 h-2 rounded-full shrink-0 ${trace.status === "success" ? "bg-green-500" : "bg-red-500"}`} />
                  <div className="min-w-0">
                    <p className="font-mono text-xs text-muted-foreground truncate">{trace.trace_id || trace.id.slice(0, 12)}</p>
                    <p className="text-sm font-medium truncate">{trace.model_id}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatLatency(trace.latency_ms)}</span>
                  <span>{formatTokens(trace.input_tokens + trace.output_tokens)}</span>
                </div>
              </button>
            ))}
            {list.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                No traces recorded yet. Send some requests through the gateway to see them here.
              </div>
            )}
          </div>
        </GlassCard>

        {/* Detail + waterfall */}
        <GlassCard>
          {selected ? (
            <div className="space-y-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold">{selected.model_id}</h3>
                    <StatusBadge status={selected.status} />
                  </div>
                  <p className="font-mono text-xs text-muted-foreground mt-1">{selected.trace_id || selected.id}</p>
                </div>
                <button
                  onClick={() => router.push(`/playground?model=${encodeURIComponent(selected.model_id)}`)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-sm hover:bg-primary/20 transition-colors"
                >
                  <RotateCw className="w-3.5 h-3.5" /> Replay
                </button>
              </div>

              {/* Waterfall */}
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">Lifecycle Waterfall</p>
                <div className="space-y-1.5">
                  {spans.map((s) => (
                    <div key={s.name} className="flex items-center gap-3 text-xs">
                      <span className="w-24 shrink-0 text-muted-foreground">{s.name}</span>
                      <div className="flex-1 h-4 bg-muted/40 rounded relative overflow-hidden">
                        <div
                          className={cn("h-full rounded", s.status === "error" ? "bg-red-500" : "bg-blue-500")}
                          style={{ marginLeft: `${(s.start_ms / maxTotal) * 100}%`, width: `${(s.duration_ms / maxTotal) * 100}%` }}
                        />
                      </div>
                      <span className="w-14 shrink-0 text-right font-mono">{formatLatency(s.duration_ms)}</span>
                    </div>
                  ))}
                  <div className="flex items-center gap-3 text-xs pt-1 border-t border-border/50">
                    <span className="w-24 shrink-0 font-medium">Total</span>
                    <div className="flex-1" />
                    <span className="w-14 shrink-0 text-right font-mono font-medium">{formatLatency(maxTotal)}</span>
                  </div>
                </div>
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                <Meta label="Cost" value={formatCurrency(selected.cost_usd)} />
                <Meta label="Tokens" value={`${formatTokens(selected.input_tokens)} → ${formatTokens(selected.output_tokens)}`} />
                <Meta label="TTFT" value={selected.ttft_ms == null ? "—" : formatLatency(selected.ttft_ms)} />
                <Meta label="Requested" value={new Date(selected.requested_at).toLocaleString()} />
              </div>

              {selected.error_message && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400 font-mono">
                  {selected.error_message}
                </div>
              )}

              {selected.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {selected.tags.map((tag) => (
                    <span key={tag} className="px-2 py-0.5 rounded-full text-xs bg-muted text-muted-foreground">{tag}</span>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">Select a trace to inspect its waterfall.</div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-3 rounded-lg bg-background/50">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-mono mt-1 truncate">{value}</p>
    </div>
  );
}
