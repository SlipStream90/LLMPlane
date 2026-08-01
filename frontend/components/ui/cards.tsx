"use client";

import { cn, formatNumber, formatCurrency, formatLatency, formatTokens } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KpiCardProps {
  title: string;
  value: number | string;
  format?: "number" | "currency" | "latency" | "tokens" | "percent";
  trend?: number;
  icon?: React.ReactNode;
  className?: string;
}

function formatValue(value: number | string, format: string): string {
  if (typeof value === "string") return value;
  switch (format) {
    case "currency": return formatCurrency(value);
    case "latency": return formatLatency(value);
    case "tokens": return formatTokens(value);
    case "percent": return value.toFixed(1) + "%";
    default: return formatNumber(value);
  }
}

export function KpiCard({ title, value, format = "number", trend, icon, className }: KpiCardProps) {
  return (
    <div className={cn("kpi-card", className)}>
      <div className="flex items-start justify-between">
        <div>
          <p className="stat-label">{title}</p>
          <p className="stat-value mt-2">{formatValue(value, format)}</p>
        </div>
        {icon && (
          <div className="p-2 rounded-lg bg-primary/10 text-primary">{icon}</div>
        )}
      </div>
      {trend !== undefined && (
        <div className="flex items-center gap-1 mt-3 text-sm">
          {trend > 0 ? (
            <TrendingUp className="w-4 h-4 text-green-500" />
          ) : trend < 0 ? (
            <TrendingDown className="w-4 h-4 text-red-500" />
          ) : (
            <Minus className="w-4 h-4 text-muted-foreground" />
          )}
          <span className={cn(
            trend > 0 ? "text-green-500" : trend < 0 ? "text-red-500" : "text-muted-foreground"
          )}>
            {Math.abs(trend).toFixed(1)}%
          </span>
          <span className="text-muted-foreground">vs yesterday</span>
        </div>
      )}
    </div>
  );
}

interface GlassCardProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}

export function GlassCard({ title, description, children, className, action }: GlassCardProps) {
  return (
    <div className={cn("glass rounded-xl p-6", className)}>
      {(title || action) && (
        <div className="flex items-center justify-between mb-4">
          <div>
            {title && <h3 className="section-header">{title}</h3>}
            {description && <p className="text-sm text-muted-foreground mt-1">{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

type StatusBadgeVariant = "success" | "warning" | "error" | "info" | "default";

const statusVariants: Record<string, StatusBadgeVariant> = {
  healthy: "success",
  running: "success",
  success: "success",
  active: "success",
  degraded: "warning",
  pending: "warning",
  downloading: "warning",
  down: "error",
  error: "error",
  failed: "error",
  stopped: "error",
  unknown: "default",
};

const variantClasses: Record<StatusBadgeVariant, string> = {
  success: "bg-green-500/10 text-green-500 border-green-500/20",
  warning: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20",
  error: "bg-red-500/10 text-red-500 border-red-500/20",
  info: "bg-blue-500/10 text-blue-500 border-blue-500/20",
  default: "bg-muted text-muted-foreground border-border",
};

export function StatusBadge({ status }: { status: string }) {
  const variant = statusVariants[status] || "default";
  return (
    <span className={cn(
      "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border",
      variantClasses[variant]
    )}>
      <span className={cn(
        "w-1.5 h-1.5 rounded-full mr-1.5",
        variant === "success" && "bg-green-500",
        variant === "warning" && "bg-yellow-500",
        variant === "error" && "bg-red-500",
        variant === "info" && "bg-blue-500",
        variant === "default" && "bg-muted-foreground",
      )} />
      {status}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-md", className)} />;
}

export function LoadingPage() {
  return (
    <div className="page-container">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="kpi-card">
            <Skeleton className="h-4 w-24 mb-3" />
            <Skeleton className="h-8 w-32" />
          </div>
        ))}
      </div>
      <Skeleton className="h-64 w-full rounded-xl" />
    </div>
  );
}
