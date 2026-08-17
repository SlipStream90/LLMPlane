"use client";

import { useDashboard } from "@/hooks/useDashboard";
import { KpiCard, GlassCard, LoadingPage } from "@/components/ui/cards";
import { formatCurrency, formatLatency, formatNumber } from "@/lib/utils";
import { Activity, DollarSign, Clock, CheckCircle, Zap, Server, Cpu } from "lucide-react";
import { Chart } from "@/components/shared/Chart";

export default function DashboardPage() {
  const { data: summary, isLoading } = useDashboard();

  if (isLoading) return <LoadingPage />;

  const s = summary?.kpis ?? {
    total_requests: 0,
    total_cost: 0,
    avg_latency_ms: 0,
    error_rate: 0,
  };

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
        <KpiCard title="Total Requests" value={s.total_requests || 0} format="number" icon={<Activity className="w-5 h-5" />} />
        <KpiCard title="Total Cost" value={s.total_cost || 0} format="currency" icon={<DollarSign className="w-5 h-5" />} />
        <KpiCard title="Avg Latency" value={s.avg_latency_ms || 0} format="latency" icon={<Clock className="w-5 h-5" />} />
        <KpiCard title="Error Rate" value={s.error_rate || 0} format="percent" icon={<CheckCircle className="w-5 h-5" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard title="Request Volume" description="Requests over time">
          <Chart
            option={{
              tooltip: { trigger: "axis" },
              xAxis: { type: "category", data: (summary?.request_over_time || []).map((d: any) => d.timestamp) },
              yAxis: { type: "value" },
              series: [{ type: "line", data: (summary?.request_over_time || []).map((d: any) => d.count), smooth: true, areaStyle: { opacity: 0.2 } }],
              grid: { left: 50, right: 20, top: 10, bottom: 30 },
            }}
            height="300px"
          />
        </GlassCard>

        <GlassCard title="Cost Over Time" description="Spending trend">
          <Chart
            option={{
              tooltip: { trigger: "axis" },
              xAxis: { type: "category", data: (summary?.cost_over_time || []).map((d: any) => d.timestamp) },
              yAxis: { type: "value", axisLabel: { formatter: "${value}" } },
              series: [{ type: "line", data: (summary?.cost_over_time || []).map((d: any) => d.cost), smooth: true, areaStyle: { opacity: 0.2 }, color: "#10b981" }],
              grid: { left: 60, right: 20, top: 10, bottom: 30 },
            }}
            height="300px"
          />
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard title="Model Usage" description="Top models by request count">
          <Chart
            option={{
              tooltip: { trigger: "item" },
              series: [{
                type: "pie",
                radius: ["40%", "70%"],
                data: (summary?.model_usage || []).map((m: any) => ({ name: m.model, value: m.requests })),
                label: { color: "#94a3b8" },
              }],
            }}
            height="300px"
          />
        </GlassCard>

        <GlassCard title="Latency Distribution" description="Response time histogram">
          <Chart
            option={{
              tooltip: { trigger: "axis" },
              xAxis: { type: "category", data: (summary?.latency_histogram || []).map((d: any) => d.bucket) },
              yAxis: { type: "value" },
              series: [{ type: "bar", data: (summary?.latency_histogram || []).map((d: any) => d.count), color: "#8b5cf6" }],
              grid: { left: 50, right: 20, top: 10, bottom: 30 },
            }}
            height="300px"
          />
        </GlassCard>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-500/10"><CheckCircle className="w-5 h-5 text-green-500" /></div>
            <div>
              <p className="text-sm text-muted-foreground">Active Models</p>
              <p className="text-xl font-bold">{(summary?.model_usage || []).length}</p>
            </div>
          </div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/10"><Zap className="w-5 h-5 text-blue-500" /></div>
            <div>
              <p className="text-sm text-muted-foreground">Providers</p>
              <p className="text-xl font-bold">{(summary as any)?.provider_count ?? "—"}</p>
            </div>
          </div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/10"><Server className="w-5 h-5 text-purple-500" /></div>
            <div>
              <p className="text-sm text-muted-foreground">Deployments</p>
              <p className="text-xl font-bold">{(summary as any)?.deployment_count ?? "—"}</p>
            </div>
          </div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-yellow-500/10"><Cpu className="w-5 h-5 text-yellow-500" /></div>
            <div>
              <p className="text-sm text-muted-foreground">GPU Util</p>
              <p className="text-xl font-bold">{(summary as any)?.gpu_utilization != null ? `${(summary as any).gpu_utilization}%` : "—"}</p>
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
