"use client";

import { useMemo, useState } from "react";
import { useLogs, type LogEntry, type LogFilters } from "@/hooks/useLogs";
import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Search, Filter, Download, Circle, X, Radio } from "lucide-react";
import { cn } from "@/lib/utils";

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
const SERVICES = ["gateway", "provider", "model", "deployment", "evaluation", "worker", "application", "infrastructure"];

const LEVEL_STYLES: Record<string, string> = {
  DEBUG: "text-slate-400",
  INFO: "text-blue-400",
  WARNING: "text-yellow-400",
  ERROR: "text-red-400",
  CRITICAL: "text-red-500 font-bold",
};

function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function LogsPage() {
  const [q, setQ] = useState("");
  const [level, setLevel] = useState("");
  const [service, setService] = useState("");
  const [live, setLive] = useState(false);
  const [selected, setSelected] = useState<LogEntry | null>(null);

  const filters: LogFilters = useMemo(
    () => ({ q: q || undefined, level: level || undefined, service: service || undefined, limit: 500 }),
    [q, level, service]
  );

  const { data: logs, isLoading } = useLogs(filters, live);

  if (isLoading) return <LoadingPage />;

  const entries = logs || [];
  const filtered = entries; // server already applied filters

  const exportAs = (fmt: "json" | "csv" | "txt" | "ndjson") => {
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    if (fmt === "json") download(`logs-${stamp}.json`, JSON.stringify(filtered, null, 2), "application/json");
    if (fmt === "ndjson") download(`logs-${stamp}.ndjson`, filtered.map((e) => JSON.stringify(e)).join("\n"), "application/x-ndjson");
    if (fmt === "csv") {
      const keys = ["timestamp", "level", "service", "request_id", "trace_id", "provider", "model", "message"];
      const rows = [keys.join(",")].concat(
        filtered.map((e) => keys.map((k) => `"${String((e as any)[k] ?? "").replace(/"/g, '""')}"`).join(","))
      );
      download(`logs-${stamp}.csv`, rows.join("\n"), "text/csv");
    }
    if (fmt === "txt") {
      const txt = filtered
        .map((e) => `${e.timestamp ?? ""} ${e.level ?? ""} [${e.service ?? "-"}] ${e.message ?? ""}`)
        .join("\n");
      download(`logs-${stamp}.txt`, txt, "text/plain");
    }
  };

  return (
    <div className="page-container !max-w-none h-[calc(100vh-3.5rem)] flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Log Explorer</h1>
          <p className="text-muted-foreground">Search, filter and export structured logs</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setLive((v) => !v)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm",
              live ? "bg-green-500/10 border-green-500/40 text-green-400" : "border-border hover:bg-muted"
            )}
          >
            <Radio className="w-4 h-4" /> {live ? "Live" : "Live off"}
          </button>
          <div className="relative group">
            <Download className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <select
              onChange={(e) => e.target.value && exportAs(e.target.value as any)}
              defaultValue=""
              className="pl-8 pr-3 py-1.5 rounded-lg border border-border text-sm appearance-none bg-background/50"
            >
              <option value="" disabled>Export</option>
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
              <option value="txt">TXT</option>
              <option value="ndjson">NDJSON</option>
            </select>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Full-text search…"
            className="pl-9 pr-4 py-2 rounded-lg bg-background/50 border border-border/50 text-sm w-full"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <select value={level} onChange={(e) => setLevel(e.target.value)} className="pl-9 pr-8 py-2 rounded-lg bg-background/50 border border-border/50 text-sm appearance-none">
            <option value="">All levels</option>
            {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <select value={service} onChange={(e) => setService(e.target.value)} className="pl-9 pr-8 py-2 rounded-lg bg-background/50 border border-border/50 text-sm appearance-none">
            <option value="">All services</option>
            {SERVICES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      <div className="relative flex-1 rounded-xl border border-border overflow-hidden bg-[#05070d] min-h-0">
        <div className="h-full overflow-y-auto font-mono text-xs divide-y divide-border/40">
          {filtered.map((e, i) => (
            <button
              key={i}
              onClick={() => setSelected(e)}
              className={cn(
                "w-full text-left px-4 py-2 flex items-start gap-3 hover:bg-accent/20 transition-colors",
                selected === e && "bg-accent/30"
              )}
            >
              <span className="text-muted-foreground shrink-0 w-20">{e.timestamp?.slice(11, 19) ?? "--:--:--"}</span>
              <Circle className={cn("w-2 h-2 mt-1 shrink-0 fill-current", LEVEL_STYLES[e.level ?? "INFO"])} />
              <span className={cn("shrink-0 w-16", LEVEL_STYLES[e.level ?? "INFO"])}>{e.level ?? "INFO"}</span>
              <span className="text-muted-foreground shrink-0 w-28 truncate">[{e.service ?? "-"}]</span>
              <span className="flex-1 truncate text-foreground/90">{e.message ?? ""}</span>
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              No log entries. Configure <code>LOG_FILE</code> to stream structured JSON logs into the explorer.
            </div>
          )}
        </div>
      </div>

      {/* Detail panel */}
      <div
        className={cn(
          "absolute top-0 right-0 h-full w-96 max-w-[90vw] border-l border-border bg-card/95 backdrop-blur-xl shadow-2xl transition-transform duration-300 z-30",
          selected ? "translate-x-0" : "translate-x-full"
        )}
      >
        {selected && (
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Circle className={cn("w-2.5 h-2.5 fill-current", LEVEL_STYLES[selected.level ?? "INFO"])} />
                <span className={cn("text-sm font-semibold", LEVEL_STYLES[selected.level ?? "INFO"])}>{selected.level}</span>
              </div>
              <button onClick={() => setSelected(null)} className="p-1.5 rounded-md hover:bg-muted"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-4 space-y-3 overflow-y-auto flex-1 text-sm">
              <Detail label="Timestamp" value={selected.timestamp} />
              <Detail label="Service" value={selected.service} />
              <Detail label="Provider" value={selected.provider} />
              <Detail label="Model" value={selected.model} />
              <Detail label="Request ID" value={selected.request_id} />
              <Detail label="Trace ID" value={selected.trace_id} />
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Message</p>
                <p className="font-mono whitespace-pre-wrap break-words">{selected.message}</p>
              </div>
              {Object.keys(selected.extra || {}).length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Metadata</p>
                  <pre className="text-[11px] bg-muted/50 rounded-md p-3 overflow-auto max-h-48 text-muted-foreground">
                    {JSON.stringify(selected.extra, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono truncate max-w-[60%]">{value ?? "—"}</span>
    </div>
  );
}
