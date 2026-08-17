"use client";

import { useExperiments } from "@/hooks/useExperiments";
import {
  Panel,
  PageHeader,
  StatusBadge,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { Plus, FlaskConical } from "lucide-react";

export default function ExperimentsPage() {
  const { data: experiments, isLoading, isError, error, refetch } = useExperiments();

  if (isLoading) return <LoadingPage />;

  const list = experiments || [];

  return (
    <div className="page-container">
      <PageHeader
        title="Experiments"
        description="Track and compare LLM runs."
        actions={
          <button
            disabled
            title="Creating experiments from the UI is not implemented yet — use the API."
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 disabled:pointer-events-none"
          >
            <Plus className="w-4 h-4" /> New experiment
          </button>
        }
      />

      {isError && (
        <ErrorState title="Could not load experiments" error={error} onRetry={refetch} />
      )}

      {!isError && list.length === 0 && (
        <EmptyState
          icon={<FlaskConical className="w-5 h-5" />}
          title="No experiments yet"
          description="Experiments group related runs so their results can be compared side by side."
        />
      )}

      {!isError && list.length > 0 && (
        <Panel title="All experiments">
          <div className="space-y-2">
            {list.map((exp) => (
              <div
                key={exp.id}
                className="flex items-center justify-between gap-4 p-4 rounded-md border border-border"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-md bg-primary-subtle flex items-center justify-center shrink-0">
                    <FlaskConical className="w-4 h-4 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium truncate">{exp.name}</p>
                    <p className="text-xs text-muted-foreground tabular">
                      {exp.runs_count} runs
                    </p>
                  </div>
                </div>
                <StatusBadge status={exp.status} />
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
