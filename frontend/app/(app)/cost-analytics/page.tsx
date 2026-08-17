"use client";

import { useState } from "react";
import {
  Panel,
  KpiCard,
  PageHeader,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { DollarSign, TrendingDown, Calendar, TrendingUp } from "lucide-react";
import { Chart } from "@/components/shared/Chart";
import { TIME_RANGES, type TimeRange } from "@/lib/constants";
import { cn } from "@/lib/utils";
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
      <PageHeader
        title="Cost Analytics"
        description="Track and optimize your LLM spending."
        actions={
          <div className="flex items-center gap-1 p-1 rounded-md bg-surface-2">
            {TIME_RANGES.map((tr) => (
              <button
                key={tr.value}
                onClick={() => setTimeRange(tr.value)}
                aria-pressed={timeRange === tr.value}
                className={cn(
                  "px-2.5 py-1 rounded text-sm font-medium transition-colors",
                  timeRange === tr.value
                    ? "bg-surface-1 text-foreground shadow-elev-1"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {tr.label}
              </button>
            ))}
          </div>
        }
      />

      {breakdown.isError && (
        <ErrorState
          title="Could not load cost data"
          error={breakdown.error}
          onRetry={breakdown.refetch}
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
        <Panel title="Cost Over Time" className="lg:col-span-2">
          {points.length === 0 ? (
            <EmptyState
              title="No spend recorded"
              description="Nothing was billed in this period. Widen the time range or send traffic through the gateway."
              className="h-[300px] py-0"
            />
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
                  },
                ],
                grid: { left: 60, right: 20, top: 10, bottom: 30 },
              }}
              height="300px"
            />
          )}
        </Panel>

        <Panel title="Cost by Model">
          {items.length === 0 ? (
            <EmptyState
              title="No spend recorded"
              description="Per-model spend appears once requests are billed in this period."
              className="h-[300px] py-0"
            />
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
                    itemStyle: { borderWidth: 0 },
                    label: { show: false },
                    data: items.map((i) => ({ name: i.key, value: i.cost_usd })),
                  },
                ],
              }}
              height="300px"
            />
          )}
        </Panel>
      </div>
    </div>
  );
}
