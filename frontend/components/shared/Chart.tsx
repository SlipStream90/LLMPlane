"use client";

import EChartsReact from "echarts-for-react";
import { Skeleton } from "@/components/ui/skeleton";

export interface ChartProps {
  option: Record<string, unknown>;
  height?: string;
  loading?: boolean;
  className?: string;
}

/** Shared palette so series colors are consistent across every chart. */
const PALETTE = [
  "#3b82f6",
  "#10b981",
  "#8b5cf6",
  "#f59e0b",
  "#ec4899",
  "#06b6d4",
  "#ef4444",
  "#84cc16",
];

const AXIS_THEME = {
  axisLine: { lineStyle: { color: "#334155" } },
  axisLabel: { color: "#94a3b8" },
  splitLine: { lineStyle: { color: "#1e293b" } },
};

const BASE_THEME = {
  backgroundColor: "transparent",
  textStyle: { color: "#94a3b8" },
  legend: { textStyle: { color: "#94a3b8" } },
  tooltip: {
    backgroundColor: "#0f172a",
    borderColor: "#1e293b",
    textStyle: { color: "#e2e8f0" },
  },
};

/** Merge theme defaults *under* a caller-supplied object, one level deep. */
function withDefaults(
  defaults: Record<string, unknown>,
  value: unknown
): unknown {
  if (Array.isArray(value)) {
    return value.map((v) => withDefaults(defaults, v));
  }
  if (value && typeof value === "object") {
    return { ...defaults, ...(value as Record<string, unknown>) };
  }
  return value;
}

export function Chart({ option, height = "400px", loading, className }: ChartProps) {
  if (loading) {
    return <Skeleton className="w-full rounded-lg" style={{ height }} />;
  }

  // Axis styling is applied only when the caller actually declared an axis.
  // Spreading xAxis/yAxis unconditionally made ECharts render a full cartesian
  // grid behind axis-less charts — the stray axes around the donut.
  const themed: Record<string, unknown> = {
    color: PALETTE,
    ...BASE_THEME,
    ...option,
    backgroundColor: "transparent",
  };

  if (option.tooltip) {
    themed.tooltip = { ...BASE_THEME.tooltip, ...(option.tooltip as object) };
  }
  if (option.xAxis) themed.xAxis = withDefaults(AXIS_THEME, option.xAxis);
  if (option.yAxis) themed.yAxis = withDefaults(AXIS_THEME, option.yAxis);

  return (
    <div className={className}>
      <EChartsReact
        option={themed}
        notMerge
        style={{ height, width: "100%" }}
        opts={{ renderer: "svg" }}
      />
    </div>
  );
}
