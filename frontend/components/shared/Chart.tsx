"use client";

import EChartsReact from "echarts-for-react";
import { Skeleton } from "@/components/ui/skeleton";

export interface ChartProps {
  option: Record<string, unknown>;
  height?: string;
  loading?: boolean;
  className?: string;
}

const DARK_THEME = {
  backgroundColor: "transparent",
  textStyle: { color: "#94a3b8" },
  legend: { textStyle: { color: "#94a3b8" } },
  xAxis: {
    axisLine: { lineStyle: { color: "#334155" } },
    axisLabel: { color: "#94a3b8" },
    splitLine: { lineStyle: { color: "#1e293b" } },
  },
  yAxis: {
    axisLine: { lineStyle: { color: "#334155" } },
    axisLabel: { color: "#94a3b8" },
    splitLine: { lineStyle: { color: "#1e293b" } },
  },
};

export function Chart({ option, height = "400px", loading, className }: ChartProps) {
  if (loading) {
    return <Skeleton className={`w-full rounded-lg`} style={{ height }} />;
  }

  const themedOption = {
    ...DARK_THEME,
    ...option,
    backgroundColor: "transparent",
  };

  return (
    <div className={className}>
      <EChartsReact
        option={themedOption}
        style={{ height, width: "100%" }}
        opts={{ renderer: "svg" }}
      />
    </div>
  );
}
