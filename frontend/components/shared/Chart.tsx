"use client";

import EChartsReact from "echarts-for-react";
import { useTheme } from "next-themes";
import { Skeleton } from "@/components/ui/skeleton";
import { CHART_COLORS } from "@/lib/constants";

export interface ChartProps {
  option: Record<string, unknown>;
  height?: string;
  loading?: boolean;
  className?: string;
}

/*
 * Series colours come from `CHART_COLORS` rather than a local list. This file
 * previously defined its own third palette, so the same logical series could be
 * one colour in an ECharts panel and another in the legend beside it.
 *
 * ECharts cannot read CSS custom properties, so the chrome colours below are
 * resolved per theme instead of inherited. They were formerly hardcoded to dark
 * slate values, which left axis labels and tooltips unreadable in light mode.
 */
const CHROME = {
  dark: {
    axisLine: "#3a4152",
    axisLabel: "#9aa3b8",
    splitLine: "#2a303e",
    text: "#9aa3b8",
    tooltipBg: "#1b202b",
    tooltipBorder: "#2f3644",
    tooltipText: "#e8eaf0",
  },
  light: {
    axisLine: "#d3d8e0",
    axisLabel: "#5b6478",
    splitLine: "#e8ebf0",
    text: "#5b6478",
    tooltipBg: "#ffffff",
    tooltipBorder: "#d3d8e0",
    tooltipText: "#252a35",
  },
} as const;

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
  const { resolvedTheme } = useTheme();
  const c = CHROME[resolvedTheme === "light" ? "light" : "dark"];

  if (loading) {
    return <Skeleton className="w-full rounded-lg" style={{ height }} />;
  }

  const axisTheme = {
    axisLine: { lineStyle: { color: c.axisLine } },
    axisLabel: { color: c.axisLabel },
    splitLine: { lineStyle: { color: c.splitLine } },
  };

  const baseTheme = {
    backgroundColor: "transparent",
    textStyle: { color: c.text },
    legend: { textStyle: { color: c.text } },
    tooltip: {
      backgroundColor: c.tooltipBg,
      borderColor: c.tooltipBorder,
      textStyle: { color: c.tooltipText },
    },
  };

  // Axis styling is applied only when the caller actually declared an axis.
  // Spreading xAxis/yAxis unconditionally made ECharts render a full cartesian
  // grid behind axis-less charts — the stray axes around the donut.
  const themed: Record<string, unknown> = {
    color: CHART_COLORS,
    ...baseTheme,
    ...option,
    backgroundColor: "transparent",
  };

  if (option.tooltip) {
    themed.tooltip = { ...baseTheme.tooltip, ...(option.tooltip as object) };
  }
  if (option.xAxis) themed.xAxis = withDefaults(axisTheme, option.xAxis);
  if (option.yAxis) themed.yAxis = withDefaults(axisTheme, option.yAxis);

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
