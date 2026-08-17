"use client";

import { useDashboard, useDashboardTimeseries } from "@/hooks/useDashboard";
import { KpiCard, GlassCard, LoadingPage } from "@/components/ui/cards";
import { Activity, DollarSign, Clock, CheckCircle, Zap, Server, Cpu } from "lucide-react";
import { Chart } from "@/components/shared/Chart";

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
  const { data: summary, isLoading, isError, error } = useDashboard();
  const series = useDashboardTimeseries("24h");

  if (isLoading) return <LoadingPage />;

  if (isError) {
    return (
      <div className="page-container">
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <GlassCard title="Could not load dashboard">
          <p className="text-sm text-red-400">{(error as Error).message}</p>
          <p className="text-sm text-muted-foreground mt-2">
            Check that <code>NEXT_PUBLIC_API_URL</code> points at your backend and that
            your API key is set.
          </p>
        </GlassCard>
      </div>
    );
  }

  const points = series.data?.points ?? [];
  const modelUsage = summary?.model_usage ?? [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Real-time overview of your LLM infrastructure</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Live
        </div>
      </div>

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
        <GlassCard title="Request Volume" description="Requests over the last 24h">
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
        </GlassCard>

        <GlassCard title="Cost Over Time" description="Spending trend">
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
                    color: "#10b981",
                  },
                ],
                grid: { left: 60, right: 20, top: 10, bottom: 30 },
              }}
              height="300px"
            />
          </ChartOrEmpty>
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard title="Model Usage" description="Top models by request count">
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
                    itemStyle: { borderColor: "#0b0f19", borderWidth: 2 },
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
        </GlassCard>

        <GlassCard title="Errors Over Time" description="Failed requests per bucket">
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
                    color: "#ef4444",
                  },
                ],
                grid: { left: 50, right: 20, top: 10, bottom: 30 },
              }}
              height="300px"
            />
          </ChartOrEmpty>
        </GlassCard>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-500/10">
              <CheckCircle className="w-5 h-5 text-green-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Success Rate</p>
              <p className="text-xl font-bold">
                {summary ? `${summary.success_rate_pct.toFixed(1)}%` : "—"}
              </p>
            </div>
          </div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/10">
              <Zap className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Req / min</p>
              <p className="text-xl font-bold">
                {summary ? summary.requests_per_minute.toFixed(1) : "—"}
              </p>
            </div>
          </div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/10">
              <Server className="w-5 h-5 text-purple-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Active Deployments</p>
              <p className="text-xl font-bold">{summary?.active_deployments ?? "—"}</p>
            </div>
          </div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-yellow-500/10">
              <Cpu className="w-5 h-5 text-yellow-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">GPU Util</p>
              <p className="text-xl font-bold">
                {summary?.gpu_util_pct_avg != null
                  ? `${Math.round(summary.gpu_util_pct_avg)}%`
                  : "—"}
              </p>
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
