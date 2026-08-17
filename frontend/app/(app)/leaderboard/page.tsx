"use client";

import { useEvaluations } from "@/hooks/useEvaluations";
import {
  Panel,
  PageHeader,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { Trophy } from "lucide-react";
import { TONE_CLASSES, type Tone } from "@/lib/status";
import { cn } from "@/lib/utils";

/** Podium tints reuse the tone ramp instead of raw gold/silver/bronze literals. */
const PODIUM: Tone[] = ["warning", "neutral", "danger"];

export default function LeaderboardPage() {
  const { data: evaluations, isLoading, isError, error, refetch } = useEvaluations();

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
      <PageHeader
        title="Leaderboard"
        description="Model rankings by average evaluation score."
      />

      {isError && (
        <ErrorState title="Could not load evaluations" error={error} onRetry={refetch} />
      )}

      {!isError && ranked.length === 0 && (
        <EmptyState
          icon={<Trophy className="w-5 h-5" />}
          title="No models ranked yet"
          description="Once evaluations are recorded, models are ranked here by their mean score."
        />
      )}

      {!isError && ranked.length > 0 && (
        <Panel flush>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground w-12">
                    #
                  </th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">
                    Model
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground">
                    Avg Score
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground">
                    Evaluations
                  </th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((row, i) => {
                  const podium = i < 3 ? TONE_CLASSES[PODIUM[i]] : null;
                  return (
                    <tr
                      key={row.model}
                      className="border-b border-border last:border-0 hover:bg-surface-2 transition-colors"
                    >
                      <td className="py-3 px-4">
                        {podium ? (
                          <span
                            className={cn(
                              "w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold tabular",
                              podium.bg,
                              podium.text
                            )}
                          >
                            {i + 1}
                          </span>
                        ) : (
                          <span className="text-muted-foreground tabular">{i + 1}</span>
                        )}
                      </td>
                      <td className="py-3 px-4 font-medium">{row.model}</td>
                      <td className="py-3 px-4 text-right font-medium tabular">
                        {row.avgScore.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right text-muted-foreground tabular">
                        {row.count}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
