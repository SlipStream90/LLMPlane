"use client";

import { useEvaluations } from "@/hooks/useEvaluations";
import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Trophy, TrendingUp, TrendingDown, Minus } from "lucide-react";

export default function LeaderboardPage() {
  const { data: evaluations, isLoading } = useEvaluations();

  if (isLoading) return <LoadingPage />;

  const list = evaluations || [];
  // Group by model and compute averages
  const modelMap = new Map<string, { model: string; avgScore: number; count: number }>();
  list.forEach((e) => {
    const existing = modelMap.get(e.model);
    if (existing) {
      existing.avgScore += e.score;
      existing.count++;
    } else {
      modelMap.set(e.model, { model: e.model, avgScore: e.score, count: 1 });
    }
  });
  const ranked = Array.from(modelMap.values())
    .map((m) => ({ ...m, avgScore: m.avgScore / m.count }))
    .sort((a, b) => b.avgScore - a.avgScore);

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Leaderboard</h1>
          <p className="text-muted-foreground">Model rankings by quality score</p>
        </div>
      </div>

      <GlassCard>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50">
                <th className="text-left py-3 px-4 font-medium text-muted-foreground w-12">#</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Model</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Avg Score</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Evaluations</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((row, i) => (
                <tr key={row.model} className="border-b border-border/30 hover:bg-accent/30 transition-colors">
                  <td className="py-3 px-4">
                    {i < 3 ? (
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${i === 0 ? "bg-yellow-500/20 text-yellow-500" : i === 1 ? "bg-gray-400/20 text-gray-400" : "bg-orange-500/20 text-orange-500"}`}>
                        {i + 1}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">{i + 1}</span>
                    )}
                  </td>
                  <td className="py-3 px-4 font-medium">{row.model}</td>
                  <td className="py-3 px-4 text-right">
                    <span className="font-medium text-green-500">{row.avgScore.toFixed(2)}</span>
                  </td>
                  <td className="py-3 px-4 text-right text-muted-foreground">{row.count}</td>
                </tr>
              ))}
              {ranked.length === 0 && (
                <tr><td colSpan={4} className="py-12 text-center text-muted-foreground">No models ranked yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
}
