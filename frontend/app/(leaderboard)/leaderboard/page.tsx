"use client";

import { useLeaderboard } from "@/hooks/use-api";
import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Trophy, TrendingUp, TrendingDown, Minus } from "lucide-react";

export default function LeaderboardPage() {
  const { data: leaderboard, isLoading } = useLeaderboard();

  if (isLoading) return <LoadingPage />;

  const list = leaderboard?.data || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Leaderboard</h1>
          <p className="text-muted-foreground">Model rankings by performance metrics</p>
        </div>
        <div className="flex items-center gap-2">
          {["judge_score", "cost", "latency", "reliability"].map((sort) => (
            <button
              key={sort}
              className="px-3 py-1.5 rounded-lg text-sm border border-border/50 hover:bg-accent transition-colors capitalize"
            >
              {sort.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <GlassCard>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50">
                <th className="text-left py-3 px-4 font-medium text-muted-foreground w-12">#</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Model</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Provider</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Judge Score</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Avg Latency</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Cost/1K</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Reliability</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Trend</th>
              </tr>
            </thead>
            <tbody>
              {list.map((row: any, i: number) => (
                <tr key={i} className="border-b border-border/30 hover:bg-accent/30 transition-colors">
                  <td className="py-3 px-4">
                    {i < 3 ? (
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                        i === 0 ? "bg-yellow-500/20 text-yellow-500" :
                        i === 1 ? "bg-gray-400/20 text-gray-400" :
                        "bg-orange-500/20 text-orange-500"
                      }`}>
                        {i + 1}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">{i + 1}</span>
                    )}
                  </td>
                  <td className="py-3 px-4 font-medium">{row.model_id}</td>
                  <td className="py-3 px-4 text-muted-foreground capitalize">{row.provider_type}</td>
                  <td className="py-3 px-4 text-right">
                    <span className="font-medium text-green-500">{row.judge_score?.toFixed(2) || "—"}</span>
                  </td>
                  <td className="py-3 px-4 text-right">{row.avg_latency_ms || "—"}ms</td>
                  <td className="py-3 px-4 text-right">${row.cost_per_1k?.toFixed(4) || "—"}</td>
                  <td className="py-3 px-4 text-right">{row.reliability_pct?.toFixed(1) || "—"}%</td>
                  <td className="py-3 px-4 text-right">
                    {row.trend > 0 ? (
                      <TrendingUp className="w-4 h-4 text-green-500 inline" />
                    ) : row.trend < 0 ? (
                      <TrendingDown className="w-4 h-4 text-red-500 inline" />
                    ) : (
                      <Minus className="w-4 h-4 text-muted-foreground inline" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
}
