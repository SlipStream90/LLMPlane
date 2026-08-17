"use client";

import {
  cn,
  formatNumber,
  formatCurrency,
  formatLatency,
  formatTokens,
} from "@/lib/utils";
import { toneFor, TONE_CLASSES, isTransient, type Tone } from "@/lib/status";
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Inbox } from "lucide-react";

/* ── Panel ──────────────────────────────────────────────────────────────── */

interface PanelProps {
  title?: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  action?: React.ReactNode;
  /** Removes body padding — for tables and charts that manage their own edges. */
  flush?: boolean;
}

export function Panel({
  title,
  description,
  children,
  className,
  bodyClassName,
  action,
  flush,
}: PanelProps) {
  return (
    <section className={cn("surface overflow-hidden", className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 px-5 py-4 border-b border-border">
          <div className="min-w-0">
            {title && <h3 className="section-header truncate">{title}</h3>}
            {description && (
              <p className="text-[0.8125rem] text-muted-foreground mt-0.5">{description}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className={cn(!flush && "p-5", bodyClassName)}>{children}</div>
    </section>
  );
}

/** Retained so the ~13 existing call sites keep working during the migration. */
export const GlassCard = Panel;

/* ── KPI ────────────────────────────────────────────────────────────────── */

interface KpiCardProps {
  title: string;
  value: number | string | null | undefined;
  format?: "number" | "currency" | "latency" | "tokens" | "percent";
  trend?: number;
  icon?: React.ReactNode;
  className?: string;
  /** Shown in place of the value when it is null — e.g. "No GPU detected". */
  emptyLabel?: string;
  hint?: string;
}

function formatValue(value: number | string, format: string): string {
  if (typeof value === "string") return value;
  switch (format) {
    case "currency":
      return formatCurrency(value);
    case "latency":
      return formatLatency(value);
    case "tokens":
      return formatTokens(value);
    case "percent":
      return `${value.toFixed(1)}%`;
    default:
      return formatNumber(value);
  }
}

export function KpiCard({
  title,
  value,
  format = "number",
  trend,
  icon,
  className,
  emptyLabel = "—",
  hint,
}: KpiCardProps) {
  // null is meaningful, not zero: `gpu_util_pct_avg` is deliberately null on a
  // host with no GPU (backend/app/api/v1/dashboard.py), and rendering that as
  // 0% would read as "idle GPU" rather than "no GPU".
  const isEmpty = value === null || value === undefined || value === "";

  return (
    <div className={cn("surface surface-interactive p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="stat-label">{title}</p>
        {icon && (
          <span className="p-1.5 rounded-md bg-primary-subtle text-primary shrink-0">
            {icon}
          </span>
        )}
      </div>

      <p
        className={cn(
          "stat-value mt-3",
          isEmpty && "text-subtle-foreground font-medium text-xl"
        )}
      >
        {isEmpty ? emptyLabel : formatValue(value, format)}
      </p>

      {hint && !isEmpty && (
        <p className="text-xs text-subtle-foreground mt-1.5">{hint}</p>
      )}

      {trend !== undefined && !isEmpty && (
        <div className="flex items-center gap-1.5 mt-3 text-[0.8125rem]">
          {trend > 0 ? (
            <TrendingUp className="w-3.5 h-3.5 text-success" />
          ) : trend < 0 ? (
            <TrendingDown className="w-3.5 h-3.5 text-danger" />
          ) : (
            <Minus className="w-3.5 h-3.5 text-muted-foreground" />
          )}
          <span
            className={cn(
              "tabular font-medium",
              trend > 0 ? "text-success" : trend < 0 ? "text-danger" : "text-muted-foreground"
            )}
          >
            {Math.abs(trend).toFixed(1)}%
          </span>
          <span className="text-subtle-foreground">vs yesterday</span>
        </div>
      )}
    </div>
  );
}

/* ── Status ─────────────────────────────────────────────────────────────── */

export function StatusBadge({
  status,
  className,
  label,
}: {
  status: string;
  className?: string;
  label?: string;
}) {
  const tone = toneFor(status);
  const c = TONE_CLASSES[tone];
  const transient = isTransient(status);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border capitalize",
        c.bg,
        c.text,
        c.border,
        className
      )}
    >
      <span className={cn("relative w-1.5 h-1.5 rounded-full", c.dot, transient && "pulse-ring")} />
      {label ?? status.replace(/_/g, " ")}
    </span>
  );
}

export function ToneDot({ tone, className }: { tone: Tone; className?: string }) {
  return <span className={cn("w-2 h-2 rounded-full", TONE_CLASSES[tone].dot, className)} />;
}

/* ── Page chrome ────────────────────────────────────────────────────────── */

export function PageHeader({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[1.375rem] font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="text-sm text-muted-foreground mt-1">{description}</p>
        )}
        {children}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </header>
  );
}

/* ── States ─────────────────────────────────────────────────────────────── */

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid-bg rounded-lg border border-dashed border-border",
        "flex flex-col items-center justify-center text-center px-6 py-14",
        className
      )}
    >
      <div className="p-2.5 rounded-lg bg-surface-2 text-subtle-foreground mb-3">
        {icon ?? <Inbox className="w-5 h-5" />}
      </div>
      <p className="font-medium">{title}</p>
      {description && (
        <p className="text-sm text-muted-foreground mt-1.5 max-w-md">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  error,
  onRetry,
  className,
}: {
  title?: string;
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const message =
    error instanceof Error ? error.message : typeof error === "string" ? error : "Unknown error";

  return (
    <div className={cn("surface border-danger/25 p-5", className)}>
      <div className="flex items-start gap-3">
        <span className="p-1.5 rounded-md bg-danger-subtle text-danger shrink-0">
          <AlertTriangle className="w-4 h-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-medium">{title}</p>
          <p className="text-sm text-danger mt-1 break-words">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 text-sm font-medium text-primary hover:underline"
            >
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Loading ────────────────────────────────────────────────────────────── */

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function LoadingPage() {
  return (
    <div className="page-container">
      <div className="space-y-2">
        <Skeleton className="h-7 w-52" />
        <Skeleton className="h-4 w-80" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="surface p-5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-32 mt-3" />
          </div>
        ))}
      </div>
      <Skeleton className="h-72 w-full rounded-lg" />
    </div>
  );
}
