"use client";

import { useTraces } from "@/hooks/useTraces";
import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Search, Filter, ExternalLink, Clock, ArrowRight } from "lucide-react";

export default function ObservabilityPage() {
  const { data: traces, isLoading } = useTraces();

  if (isLoading) return <LoadingPage />;

  const list = traces || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Observability</h1>
          <p className="text-muted-foreground">Request traces and lifecycle waterfall</p>
        </div>
        <a href="https://cloud.langfuse.com" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
          <ExternalLink className="w-4 h-4" /> Open Langfuse
        </a>
      </div>

      <div className="flex items-center gap-4 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input type="text" placeholder="Search by trace ID, model, or status..." className="pl-9 pr-4 py-2 rounded-lg bg-background/50 border border-border/50 text-sm w-full" />
        </div>
        <button className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
          <Filter className="w-4 h-4" /> Filters
        </button>
      </div>

      <GlassCard>
        <div className="space-y-2">
          {list.map((trace) => (
            <div key={trace.id} className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:bg-accent/30 transition-colors cursor-pointer">
              <div className="flex items-center gap-4">
                <div className={`w-2 h-2 rounded-full ${trace.status === "success" ? "bg-green-500" : "bg-red-500"}`} />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-muted-foreground">{trace.id.slice(0, 12)}...</span>
                    <span className="text-sm font-medium">{trace.model}</span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{trace.latency_ms}ms</span>
                    <span>{trace.tokens_input + trace.tokens_output} tokens</span>
                    <span>${trace.cost.toFixed(4)}</span>
                    <span>{new Date(trace.timestamp).toLocaleString()}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded-full text-xs ${trace.status === "success" ? "bg-green-500/10 text-green-500" : "bg-red-500/10 text-red-500"}`}>
                  {trace.status}
                </span>
                <ArrowRight className="w-4 h-4 text-muted-foreground" />
              </div>
            </div>
          ))}
          {list.length === 0 && (
            <div className="text-center py-12 text-muted-foreground">No traces recorded yet. Send some requests through the gateway to see them here.</div>
          )}
        </div>
      </GlassCard>
    </div>
  );
}
