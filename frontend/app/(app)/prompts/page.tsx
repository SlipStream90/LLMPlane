"use client";

import { usePrompts, useDeletePrompt } from "@/hooks/usePrompts";
import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Plus, GitBranch, History, RotateCcw, Trash2 } from "lucide-react";

export default function PromptsPage() {
  const { data: prompts, isLoading } = usePrompts();
  const deletePrompt = useDeletePrompt();

  if (isLoading) return <LoadingPage />;

  const list = prompts || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Prompts</h1>
          <p className="text-muted-foreground">Version-controlled prompt management</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
          <Plus className="w-4 h-4" /> New Prompt
        </button>
      </div>

      <GlassCard>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="section-header">Prompt Library</h3>
            <input type="text" placeholder="Search prompts..." className="px-3 py-1.5 rounded-lg bg-background/50 border border-border/50 text-sm w-64" />
          </div>
          <div className="space-y-2">
            {list.map((prompt) => (
              <div key={prompt.id} className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:bg-accent/50 transition-colors cursor-pointer">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                    <GitBranch className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <p className="font-medium">{prompt.name}</p>
                    <p className="text-xs text-muted-foreground">{prompt.version} versions · {prompt.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button className="p-2 rounded-lg hover:bg-accent transition-colors" title="Version History"><History className="w-4 h-4" /></button>
                  <button className="p-2 rounded-lg hover:bg-accent transition-colors" title="Rollback"><RotateCcw className="w-4 h-4" /></button>
                  <button onClick={() => deletePrompt.mutate(prompt.id)} className="p-2 rounded-lg hover:bg-destructive/10 hover:text-destructive transition-colors" title="Delete"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
            ))}
            {list.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">No prompts created yet.</div>
            )}
          </div>
        </div>
      </GlassCard>
    </div>
  );
}
