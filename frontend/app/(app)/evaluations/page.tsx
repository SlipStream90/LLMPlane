"use client";

import { useEvaluations } from "@/hooks/useEvaluations";
import {
  Panel,
  PageHeader,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { ClipboardCheck } from "lucide-react";
import { TONE_CLASSES } from "@/lib/status";
import { cn } from "@/lib/utils";

/** Score bands mirror the tone vocabulary rather than raw palette classes. */
function scoreTone(score: number) {
  if (score >= 0.9) return TONE_CLASSES.success;
  if (score >= 0.8) return TONE_CLASSES.warning;
  return TONE_CLASSES.danger;
}

export default function EvaluationsPage() {
  const { data: evaluations, isLoading, isError, error, refetch } = useEvaluations();

  if (isLoading) return <LoadingPage />;

  const list = evaluations || [];

  return (
    <div className="page-container">
      <PageHeader
        title="Evaluations"
        description="Evaluation scores across benchmark and experiment runs."
      />

      {isError && (
        <ErrorState title="Could not load evaluations" error={error} onRetry={refetch} />
      )}

      {!isError && list.length === 0 && (
        <EmptyState
          icon={<ClipboardCheck className="w-5 h-5" />}
          title="No evaluations yet"
          description="Scores appear here once a benchmark run finishes scoring its items."
        />
      )}

      {!isError && list.length > 0 && (
        <Panel flush>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">
                    Model
                  </th>
                  <th className="text-left py-3 px-4 font-medium text-muted-foreground">
                    Prompt
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground">
                    Score
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground">
                    Metrics
                  </th>
                  <th className="text-right py-3 px-4 font-medium text-muted-foreground">
                    Date
                  </th>
                </tr>
              </thead>
              <tbody>
                {list.map((row) => {
                  const tone = scoreTone(row.score);
                  return (
                    <tr
                      key={row.id}
                      className="border-b border-border last:border-0 hover:bg-surface-2 transition-colors"
                    >
                      <td className="py-3 px-4 font-medium">{row.model}</td>
                      <td className="py-3 px-4 text-muted-foreground">{row.prompt_name}</td>
                      <td className="py-3 px-4 text-right">
                        <span
                          className={cn(
                            "inline-block px-2 py-0.5 rounded text-xs font-medium tabular border",
                            tone.bg,
                            tone.text,
                            tone.border
                          )}
                        >
                          {row.score.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right text-xs text-muted-foreground tabular">
                        {Object.entries(row.metrics)
                          .map(([k, v]) => `${k}: ${(v as number).toFixed(2)}`)
                          .join(", ")}
                      </td>
                      <td className="py-3 px-4 text-right text-muted-foreground tabular">
                        {new Date(row.created_at).toLocaleDateString()}
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
