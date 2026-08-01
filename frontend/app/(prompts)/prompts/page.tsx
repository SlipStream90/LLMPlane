"use client";

import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Plus, GitBranch, History, RotateCcw } from "lucide-react";

export default function PromptsPage() {
  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Prompts</h1>
          <p className="text-muted-foreground">Version-controlled prompt management</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
          <Plus className="w-4 h-4" />
          New Prompt
        </button>
      </div>

      <GlassCard>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="section-header">Prompt Library</h3>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Search prompts..."
                className="px-3 py-1.5 rounded-lg bg-background/50 border border-border/50 text-sm w-64"
              />
            </div>
          </div>

          <div className="space-y-2">
            {[
              { name: "Customer Support Agent", versions: 12, lastEdited: "2 hours ago" },
              { name: "Code Review Assistant", versions: 8, lastEdited: "1 day ago" },
              { name: "Content Generator", versions: 15, lastEdited: "3 days ago" },
              { name: "Data Analysis Prompt", versions: 5, lastEdited: "1 week ago" },
            ].map((prompt, i) => (
              <div
                key={i}
                className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:bg-accent/50 transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                    <GitBranch className="w-4 h-4 text-primary" />
                  </div>
                  <div>
                    <p className="font-medium">{prompt.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {prompt.versions} versions · Last edited {prompt.lastEdited}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button className="p-2 rounded-lg hover:bg-accent transition-colors" title="Version History">
                    <History className="w-4 h-4" />
                  </button>
                  <button className="p-2 rounded-lg hover:bg-accent transition-colors" title="Rollback">
                    <RotateCcw className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </GlassCard>
    </div>
  );
}
