"use client";

import { useDashboard } from "@/hooks/useDashboard";
import { GlassCard, KpiCard, LoadingPage } from "@/components/ui/cards";
import { DollarSign, TrendingDown, Calendar, Download } from "lucide-react";
import { Chart } from "@/components/shared/Chart";
import { useState } from "react";
import { TIME_RANGES, type TimeRange } from "@/lib/constants";

export default function CostAnalyticsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>("30d");
  const { data: analytics, isLoading } = useDashboard(timeRange);

  if (isLoading) return <LoadingPage />;

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Cost Analytics</h1>
          <p className="text-muted-foreground">Track and optimize your LLM spending</p>
        </div>
        <div className="flex gap-2">
          {TIME_RANGES.map((tr) => (
            <button
              key={tr.value}
              onClick={() => setTimeRange(tr.value)}
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${timeRange === tr.value ? "bg-primary/10 border-primary/30 text-primary" : "border-border/50 hover:bg-accent"}`}
            >
              {tr.label}
            </button>
          ))}
          <button className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
            <Download className="w-4 h-4" /> Export
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KpiCard title="Total Spend" value={analytics?.kpis?.total_cost || 0} format="currency" icon={<DollarSign className="w-5 h-5" />} />
        <KpiCard title="Total Requests" value={analytics?.kpis?.total_requests || 0} format="number" icon={<Calendar className="w-5 h-5" />} />
        <KpiCard title="Avg Cost/Request" value={analytics?.kpis?.total_requests ? (analytics.kpis.total_cost / analytics.kpis.total_requests) : 0} format="currency" icon={<TrendingDown className="w-5 h-5" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard title="Cost Over Time" className="lg:col-span-2">
          <Chart
            option={{
              tooltip: { trigger: "axis" },
              xAxis: { type: "category", data: (analytics?.cost_over_time || []).map((d: any) => d.timestamp) },
              yAxis: { type: "value", axisLabel: { formatter: "${value}" } },
              series: [{ type: "line", data: (analytics?.cost_over_time || []).map((d: any) => d.cost), smooth: true, areaStyle: { opacity: 0.2 }, color: "#3b82f6" }],
              grid: { left: 60, right: 20, top: 10, bottom: 30 },
            }}
            height="300px"
          />
        </GlassCard>

        <GlassCard title="Cost by Model">
          <Chart
            option={{
              tooltip: { trigger: "item" },
              series: [{
                type: "pie",
                radius: ["40%", "70%"],
                data: (analytics?.model_usage || []).map((m: any) => ({ name: m.model, value: m.cost })),
                label: { color: "#94a3b8" },
              }],
            }}
            height="300px"
          />
        </GlassCard>
      </div>
    </div>
  );
}
