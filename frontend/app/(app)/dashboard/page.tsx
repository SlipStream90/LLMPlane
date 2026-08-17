"use client";

import { useDashboard, useDashboardTimeseries } from "@/hooks/useDashboard";
import {
  KpiCard,
  Panel,
  PageHeader,
  LoadingPage,
  ErrorState,
} from "@/components/ui/cards";
import { Activity, DollarSign, Clock, CheckCircle, Zap, Server, Cpu } from "lucide-react";
import { Chart } from "@/components/shared/Chart";
import { TONE_HEX } from "@/lib/status";
import { cn } from "@/lib/utils";

/** Renders an inline placeholder instead of an axis-less empty ECharts canvas. */
function ChartOrEmpty({
  empty,
  height = "300px",
  children,
}: {
  empty: boolean;
  height?: string;
  children: React.ReactNode;
}) {
  if (empty) {
    return (
      <div
        className="flex items-center justify-center text-sm text-muted-foreground"
        style={{ height }}
      >
        No data for this period yet.
      </div>
    );
  }
  return <>{children}</>;
}

export default function DashboardPage() {
  const { data: summary, isLoading, isError, error, refetch } = useDashboard();
  const series = useDashboardTimeseries("24h");

  if (isLoading) return <LoadingPage />;

  if (isError) {
    return (
      <div className="page-container">
        <PageHeader
          title="Dashboard"
          description="Real-time overview of your LLM infrastructure."
        />
        <ErrorState title="Could not load dashboard" error={error} onRetry={refetch} />
        <p className="text-sm text-muted-foreground">
          Check that <code className="font-mono">NEXT_PUBLIC_API_URL</code> points at your
          backend and that your API key is set.
        </p>
      </div>
    );
  }

  const points = series.data?.points ?? [];
  const modelUsage = summary?.model_usage ?? [];

  return (
    <div className="page-container">
      <PageHeader
        title="Dashboard"
        description="Real-time overview of your LLM infrastructure."
        actions={
          <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
            <span className="relative w-1.5 h-1.5 rounded-full bg-success pulse-ring" />
            Live
          </span>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Requests Today"
          value={summary?.requests_today ?? 0}
          format="number"
          icon={<Activity className="w-5 h-5" />}
        />
        <KpiCard
          title="Cost Today"
          value={summary?.cost_today_usd ?? 0}
          format="currency"
          icon={<DollarSign className="w-5 h-5" />}
        />
        <KpiCard
          title="Avg Latency"
          value={summary?.avg_latency_ms ?? 0}
          format="latency"
          icon={<Clock className="w-5 h-5" />}
        />
        <KpiCard
          title="Error Rate"
          value={summary?.error_rate_pct ?? 0}
          format="percent"
          icon={<CheckCircle className="w-5 h-5" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Request Volume" description="Requests over the last 24h">
          <ChartOrEmpty empty={points.length === 0}>
            <Chart
              option={{
                tooltip: { trigger: "axis" },
                xAxis: { type: "category", data: points.map((p) => p.bucket) },
                yAxis: { type: "value" },
                series: [
                  {
                    type: "line",
                    data: points.map((p) => p.request_count),
                    smooth: true,
                    areaStyle: { opacity: 0.2 },
                  },
                ],
                grid: { left: 50, right: 20, top: 10, bottom: 30 },
              }}
              height="300px"
            />
          </ChartOrEmpty>
        </Panel>

        <Panel title="Cost Over Time" description="Spending trend">
          <ChartOrEmpty empty={points.length === 0}>
            <Chart
              option={{
                tooltip: { trigger: "axis" },
                xAxis: { type: "category", data: points.map((p) => p.bucket) },
                yAxis: { type: "value", axisLabel: { formatter: "${value}" } },
                series: [
                  {
                    type: "line",
                    data: points.map((p) => p.cost_usd),
                    smooth: true,
                    areaStyle: { opacity: 0.2 },
                    color: TONE_HEX.success,
                  },
                ],
                grid: { left: 60, right: 20, top: 10, bottom: 30 },
              }}
              height="300px"
            />
          </ChartOrEmpty>
        </Panel>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Panel title="Model Usage" description="Top models by request count">
          <ChartOrEmpty empty={modelUsage.length === 0}>
            <Chart
              option={{
                tooltip: {
                  trigger: "item",
                  formatter: "{b}<br/>{c} requests ({d}%)",
                },
                legend: { bottom: 0, type: "scroll" },
                series: [
                  {
                    type: "pie",
                    radius: ["45%", "72%"],
                    center: ["50%", "45%"],
                    avoidLabelOverlap: true,
                    itemStyle: { borderWidth: 0 },
                    label: { show: false },
                    data: modelUsage.map((m) => ({
                      name: m.model_id,
                      value: m.request_count,
                    })),
                  },
                ],
              }}
              height="300px"
            />
          </ChartOrEmpty>
        </Panel>

        <Panel title="Errors Over Time" description="Failed requests per bucket">
          <ChartOrEmpty empty={points.length === 0}>
            <Chart
              option={{
                tooltip: { trigger: "axis" },
                xAxis: { type: "category", data: points.map((p) => p.bucket) },
                yAxis: { type: "value" },
                series: [
                  {
                    type: "bar",
                    data: points.map((p) => p.error_count),
                    color: TONE_HEX.danger,
                  },
                ],
                grid: { left: 50, right: 20, top: 10, bottom: 30 },
              }}
              height="300px"
            />
          </ChartOrEmpty>
        </Panel>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MiniStat
          label="Success Rate"
          value={summary ? `${summary.success_rate_pct.toFixed(1)}%` : "—"}
          icon={<CheckCircle className="w-5 h-5" />}
          tint="bg-success-subtle text-success"
        />
        <MiniStat
          label="Req / min"
          value={summary ? summary.requests_per_minute.toFixed(1) : "—"}
          icon={<Zap className="w-5 h-5" />}
          tint="bg-info-subtle text-info"
        />
        <MiniStat
          label="Active Deployments"
          value={summary?.active_deployments ?? "—"}
          icon={<Server className="w-5 h-5" />}
          tint="bg-primary-subtle text-primary"
        />
        <MiniStat
          label="GPU Util"
          value={
            summary?.gpu_util_pct_avg != null
              ? `${Math.round(summary.gpu_util_pct_avg)}%`
              : "—"
          }
          icon={<Cpu className="w-5 h-5" />}
          tint="bg-warning-subtle text-warning"
        />
      </div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  icon,
  tint,
}: {
  label: string;
  value: React.ReactNode;
  icon: React.ReactNode;
  tint: string;
}) {
  return (
    <div className="surface surface-interactive p-5 flex items-center gap-3">
      <span className={cn("p-2 rounded-md shrink-0", tint)}>{icon}</span>
      <div className="min-w-0">
        <p className="stat-label truncate">{label}</p>
        <p className="text-xl font-semibold tabular mt-0.5">{value}</p>
      </div>
    </div>
  );
}
