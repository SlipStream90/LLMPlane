"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { API_BASE_URL, getApiKey } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Pause, Play, ArrowDownToLine, Trash2, Loader2 } from "lucide-react";

type ConnState = "connecting" | "streaming" | "paused" | "closed" | "error";

const MAX_LINES = 2_000;

/**
 * Live container logs for a deployment.
 *
 * Uses `fetch` + a stream reader rather than `EventSource`, because the SSE
 * endpoint sits behind the same bearer auth as the rest of the API and
 * `EventSource` cannot set an Authorization header.
 *
 * The payload is double-wrapped: the worker publishes
 * `{"topic","event","data":{"line"}}` to Redis and the route relays that verbatim
 * inside the SSE `data:` field — so the actual log text is `.data.line`, not the
 * frame body. (`/logs/stream` elsewhere in the API emits a *different*, bare
 * shape; the two are not interchangeable.)
 */
export function DeploymentLogs({ deploymentId }: { deploymentId: string }) {
  const [lines, setLines] = useState<string[]>([]);
  const [state, setState] = useState<ConnState>("connecting");
  const [follow, setFollow] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const followRef = useRef(follow);
  followRef.current = follow;

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const start = useCallback(async () => {
    stop();
    const controller = new AbortController();
    abortRef.current = controller;
    setState("connecting");
    setError(null);

    try {
      const apiKey = getApiKey();
      const res = await fetch(`${API_BASE_URL}/deployments/${deploymentId}/logs?tail=200`, {
        headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : {},
        signal: controller.signal,
      });

      if (!res.ok) {
        setState("error");
        setError(
          res.status === 404
            ? "This deployment has no container to stream from yet."
            : `Log stream failed: ${res.status} ${res.statusText}`
        );
        return;
      }
      if (!res.body) {
        setState("error");
        setError("Log streaming is not supported in this browser.");
        return;
      }

      setState("streaming");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // SSE frames are separated by a blank line; keep the trailing partial.
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        const incoming: string[] = [];
        for (const frame of frames) {
          for (const raw of frame.split("\n")) {
            if (!raw.startsWith("data:")) continue;
            const payload = raw.slice(5).trim();
            if (!payload) continue;
            try {
              const parsed = JSON.parse(payload);
              const line = parsed?.data?.line ?? parsed?.line;
              if (typeof line === "string") incoming.push(line);
            } catch {
              // Heartbeats and any non-JSON frame pass through as-is.
              incoming.push(payload);
            }
          }
        }

        if (incoming.length) {
          setLines((prev) => {
            const next = [...prev, ...incoming];
            return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next;
          });
        }
      }
      setState("closed");
    } catch (e) {
      if (controller.signal.aborted) return;
      setState("error");
      setError(e instanceof Error ? e.message : "Log stream disconnected.");
    }
  }, [deploymentId, stop]);

  useEffect(() => {
    start();
    return stop;
  }, [start, stop]);

  useEffect(() => {
    if (!follow) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines, follow]);

  const paused = state === "paused";

  return (
    <div className="surface overflow-hidden">
      <header className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-border">
        <div className="flex items-center gap-2 min-w-0">
          <span className="section-header">Container logs</span>
          <StreamBadge state={state} />
        </div>

        <div className="flex items-center gap-1">
          <IconButton
            label={paused ? "Resume stream" : "Pause stream"}
            onClick={() => {
              if (paused) {
                start();
              } else {
                stop();
                setState("paused");
              }
            }}
          >
            {paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
          </IconButton>

          <IconButton
            label={follow ? "Stop following" : "Follow output"}
            active={follow}
            onClick={() => setFollow((f) => !f)}
          >
            <ArrowDownToLine className="w-3.5 h-3.5" />
          </IconButton>

          <IconButton label="Clear" onClick={() => setLines([])}>
            <Trash2 className="w-3.5 h-3.5" />
          </IconButton>
        </div>
      </header>

      {error && (
        <p className="px-4 py-2.5 text-sm text-danger border-b border-border bg-danger-subtle">
          {error}
        </p>
      )}

      <div
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
          if (!atBottom && followRef.current) setFollow(false);
        }}
        className="h-[26rem] overflow-auto bg-background-subtle px-4 py-3 font-mono text-xs leading-relaxed"
      >
        {lines.length === 0 ? (
          <p className="text-subtle-foreground">
            {state === "connecting" ? "Connecting to the log stream…" : "No output yet."}
          </p>
        ) : (
          lines.map((line, i) => (
            <div key={i} className="whitespace-pre-wrap break-all text-muted-foreground">
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function StreamBadge({ state }: { state: ConnState }) {
  const map: Record<ConnState, { label: string; cls: string }> = {
    connecting: { label: "connecting", cls: "bg-info-subtle text-info" },
    streaming: { label: "live", cls: "bg-success-subtle text-success" },
    paused: { label: "paused", cls: "bg-warning-subtle text-warning" },
    closed: { label: "ended", cls: "bg-surface-2 text-muted-foreground" },
    error: { label: "error", cls: "bg-danger-subtle text-danger" },
  };
  const { label, cls } = map[state];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[0.6875rem] font-medium",
        cls
      )}
    >
      {state === "connecting" && <Loader2 className="w-3 h-3 animate-spin" />}
      {label}
    </span>
  );
}

function IconButton({
  children,
  label,
  onClick,
  active,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      aria-pressed={active}
      className={cn(
        "p-1.5 rounded-md transition-colors",
        active
          ? "bg-primary-subtle text-primary"
          : "text-muted-foreground hover:bg-surface-2 hover:text-foreground"
      )}
    >
      {children}
    </button>
  );
}
