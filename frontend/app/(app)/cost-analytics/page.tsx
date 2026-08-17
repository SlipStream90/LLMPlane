"use client";

import { useState } from "react";
import { GlassCard, KpiCard, LoadingPage } from "@/components/ui/cards";
import { DollarSign, TrendingDown, Calendar, TrendingUp } from "lucide-react";
import { Chart } from "@/components/shared/Chart";
import { TIME_RANGES, type TimeRange } from "@/lib/constants";
import {
  useCostBreakdown,
  useCostForecast,
  useCostOverTime,
} from "@/hooks/useCostAnalytics";

export default function CostAnalyticsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>("30d");
  const breakdown = useCostBreakdown(timeRange, "model");
  const overTime = useCostOverTime(timeRange);
  const forecast = useCostForecast();

  if (breakdown.isLoading && overTime.isLoading) return <LoadingPage />;

  const items = breakdown.data?.items ?? [];
  const points = overTime.data?.points ?? [];
  const totalCost = breakdown.data?.total_cost_usd ?? 0;
  const totalRequests = items.reduce((sum, i) => sum + i.request_count, 0);

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
              className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${
                timeRange === tr.value
                  ? "bg-primary/10 border-primary/30 text-primary"
                  : "border-border/50 hover:bg-accent"
              }`}
            >
              {tr.label}
            </button>
          ))}
        </div>
      </div>

      {breakdown.isError && (
        <GlassCard title="Could not load cost data">
          <p className="text-sm text-red-400">{(breakdown.error as Error).message}</p>
        </GlassCard>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KpiCard
          title="Total Spend"
          value={totalCost}
          format="currency"
          icon={<DollarSign className="w-5 h-5" />}
        />
        <KpiCard
          title="Total Requests"
          value={totalRequests}
          format="number"
          icon={<Calendar className="w-5 h-5" />}
        />
        <KpiCard
          title="Avg Cost/Request"
          value={totalRequests ? totalCost / totalRequests : 0}
          format="currency"
          icon={<TrendingDown className="w-5 h-5" />}
        />
        <KpiCard
          title="Projected Month End"
          value={forecast.data?.projected_month_end_usd ?? 0}
          format="currency"
          icon={<TrendingUp className="w-5 h-5" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard title="Cost Over Time" className="lg:col-span-2">
          {points.length === 0 ? (
            <div className="flex items-center justify-center h-[300px] text-sm text-muted-foreground">
              No spend recorded for this period.
            </div>
          ) : (
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
                    color: "#3b82f6",
                  },
                ],
                grid: { left: 60, right: 20, top: 10, bottom: 30 },
              }}
              height="300px"
            />
          )}
        </GlassCard>

        <GlassCard title="Cost by Model">
          {items.length === 0 ? (
            <div className="flex items-center justify-center h-[300px] text-sm text-muted-foreground">
              No spend recorded for this period.
            </div>
          ) : (
            <Chart
              option={{
                tooltip: {
                  trigger: "item",
                  formatter: "{b}<br/>${c} ({d}%)",
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
                    data: items.map((i) => ({ name: i.key, value: i.cost_usd })),
                  },
                ],
              }}
              height="300px"
            />
          )}
        </GlassCard>
      </div>
    </div>
  );
}
