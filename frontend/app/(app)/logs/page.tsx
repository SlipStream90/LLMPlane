"use client";

import { useMemo, useState } from "react";
import { useLogs, type LogEntry, type LogFilters } from "@/hooks/useLogs";
import { PageHeader, LoadingPage, EmptyState, ErrorState } from "@/components/ui/cards";
import { Search, Filter, Download, Circle, X, Radio, ScrollText } from "lucide-react";
import { TONE_CLASSES, type Tone } from "@/lib/status";
import { cn } from "@/lib/utils";

const LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
const SERVICES = ["gateway", "provider", "model", "deployment", "evaluation", "worker", "application", "infrastructure"];

/** Log severities are their own vocabulary; map them onto the shared tones. */
const LEVEL_TONE: Record<string, Tone> = {
  DEBUG: "neutral",
  INFO: "info",
  WARNING: "warning",
  ERROR: "danger",
  CRITICAL: "danger",
};

function levelClass(level: string | null | undefined): string {
  const key = level ?? "INFO";
  const tone = LEVEL_TONE[key] ?? "neutral";
  return cn(TONE_CLASSES[tone].text, key === "CRITICAL" && "font-bold");
}

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

  const { data: logs, isLoading, isError, error, refetch } = useLogs(filters, live);

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
    <div className="page-container !max-w-none !space-y-0 h-[calc(100vh-3.5rem)] flex flex-col relative">
      <PageHeader
        title="Log Explorer"
        description="Search, filter and export structured logs."
        actions={
          <>
            <button
              onClick={() => setLive((v) => !v)}
              aria-pressed={live}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-sm font-medium transition-colors",
                live
                  ? cn(TONE_CLASSES.success.bg, TONE_CLASSES.success.text, TONE_CLASSES.success.border)
                  : "border-border text-muted-foreground hover:bg-surface-2 hover:text-foreground"
              )}
            >
              <Radio className="w-4 h-4" /> {live ? "Live" : "Live off"}
            </button>
            <div className="relative">
              <Download className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
              <select
                onChange={(e) => e.target.value && exportAs(e.target.value as any)}
                defaultValue=""
                aria-label="Export logs"
                disabled={filtered.length === 0}
                title={filtered.length === 0 ? "Nothing to export" : "Export the current result set"}
                className="pl-8 pr-3 py-1.5 rounded-md border border-border bg-surface-1 text-sm appearance-none disabled:opacity-50"
              >
                <option value="" disabled>Export</option>
                <option value="json">JSON</option>
                <option value="csv">CSV</option>
                <option value="txt">TXT</option>
                <option value="ndjson">NDJSON</option>
              </select>
            </div>
          </>
        }
      />

      <div className="flex items-center gap-2 my-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Full-text search…"
            aria-label="Full-text search"
            className="pl-9 pr-4 py-2 rounded-md bg-surface-1 border border-border text-sm w-full"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            aria-label="Filter by level"
            className="pl-9 pr-8 py-2 rounded-md bg-surface-1 border border-border text-sm appearance-none"
          >
            <option value="">All levels</option>
            {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <select
            value={service}
            onChange={(e) => setService(e.target.value)}
            aria-label="Filter by service"
            className="pl-9 pr-8 py-2 rounded-md bg-surface-1 border border-border text-sm appearance-none"
          >
            <option value="">All services</option>
            {SERVICES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {isError ? (
        <ErrorState title="Could not load logs" error={error} onRetry={refetch} />
      ) : (
        <div className="relative flex-1 rounded-lg border border-border overflow-hidden bg-background-subtle min-h-0">
          <div className="h-full overflow-y-auto font-mono text-xs divide-y divide-border">
            {filtered.map((e, i) => (
              <button
                key={i}
                onClick={() => setSelected(e)}
                className={cn(
                  "w-full text-left px-4 py-2 flex items-start gap-3 hover:bg-surface-2 transition-colors",
                  selected === e && "bg-surface-3"
                )}
              >
                <span className="text-muted-foreground shrink-0 w-20 tabular">
                  {e.timestamp?.slice(11, 19) ?? "--:--:--"}
                </span>
                <Circle className={cn("w-2 h-2 mt-1 shrink-0 fill-current", levelClass(e.level))} />
                <span className={cn("shrink-0 w-16", levelClass(e.level))}>{e.level ?? "INFO"}</span>
                <span className="text-muted-foreground shrink-0 w-28 truncate">[{e.service ?? "-"}]</span>
                <span className="flex-1 truncate">{e.message ?? ""}</span>
              </button>
            ))}
            {filtered.length === 0 && (
              <EmptyState
                icon={<ScrollText className="w-5 h-5" />}
                title="No log entries"
                description="Configure LOG_FILE to stream structured JSON logs into the explorer, or relax the filters above."
                className="border-0 h-full"
              />
            )}
          </div>
        </div>
      )}

      {/* Detail panel */}
      <div
        className={cn(
          "absolute top-0 right-0 h-full w-96 max-w-[90vw] border-l border-border bg-surface-1 shadow-elev-3 transition-transform duration-300 z-30",
          selected ? "translate-x-0" : "translate-x-full"
        )}
      >
        {selected && (
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <Circle className={cn("w-2.5 h-2.5 fill-current", levelClass(selected.level))} />
                <span className={cn("text-sm font-semibold", levelClass(selected.level))}>
                  {selected.level}
                </span>
              </div>
              <button
                onClick={() => setSelected(null)}
                aria-label="Close detail panel"
                className="p-1.5 rounded-md text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4 space-y-3 overflow-y-auto flex-1 text-sm">
              <Detail label="Timestamp" value={selected.timestamp} />
              <Detail label="Service" value={selected.service} />
              <Detail label="Provider" value={selected.provider} />
              <Detail label="Model" value={selected.model} />
              <Detail label="Request ID" value={selected.request_id} />
              <Detail label="Trace ID" value={selected.trace_id} />
              <div>
                <p className="text-xs uppercase tracking-wider text-subtle-foreground mb-1">Message</p>
                <p className="font-mono whitespace-pre-wrap break-words">{selected.message}</p>
              </div>
              {Object.keys(selected.extra || {}).length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-wider text-subtle-foreground mb-1">Metadata</p>
                  <pre className="text-[11px] bg-surface-2 rounded-md p-3 overflow-auto max-h-48 text-muted-foreground">
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
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="font-mono truncate max-w-[60%]">{value ?? "—"}</span>
    </div>
  );
}
