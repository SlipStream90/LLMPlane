"use client";

import { usePrompts, useDeletePrompt } from "@/hooks/usePrompts";
import {
  Panel,
  PageHeader,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { Plus, GitBranch, Trash2 } from "lucide-react";

export default function PromptsPage() {
  const { data: prompts, isLoading, isError, error, refetch } = usePrompts();
  const deletePrompt = useDeletePrompt();

  if (isLoading) return <LoadingPage />;

  const list = prompts || [];

  return (
    <div className="page-container">
      <PageHeader
        title="Prompts"
        description="Version-controlled prompt management."
        actions={
          <button
            disabled
            title="Authoring prompts from the UI is not implemented yet — create them via the API."
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 disabled:pointer-events-none"
          >
            <Plus className="w-4 h-4" /> New prompt
          </button>
        }
      />

      {isError && (
        <ErrorState title="Could not load prompts" error={error} onRetry={refetch} />
      )}

      {!isError && list.length === 0 && (
        <EmptyState
          icon={<GitBranch className="w-5 h-5" />}
          title="No prompts yet"
          description="Prompts stored here are versioned, so every edit keeps its history."
        />
      )}

      {!isError && list.length > 0 && (
        <Panel title="Prompt library">
          <div className="space-y-2">
            {list.map((prompt) => (
              <div
                key={prompt.id}
                className="flex items-center justify-between gap-4 p-4 rounded-md border border-border"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-md bg-primary-subtle flex items-center justify-center shrink-0">
                    <GitBranch className="w-4 h-4 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium truncate">{prompt.name}</p>
                    <p className="text-xs text-muted-foreground truncate">
                      <span className="tabular">{prompt.version}</span> versions ·{" "}
                      {prompt.description}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => deletePrompt.mutate(prompt.id)}
                  disabled={deletePrompt.isPending}
                  title="Delete prompt"
                  aria-label="Delete prompt"
                  className="p-2 rounded-md border border-border text-muted-foreground hover:text-danger hover:border-danger/30 hover:bg-danger-subtle transition-colors disabled:opacity-50 disabled:pointer-events-none shrink-0"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
