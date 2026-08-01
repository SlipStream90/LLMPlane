"use client";

import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Plus, FlaskConical, Search, Filter } from "lucide-react";

export default function ExperimentsPage() {
  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Experiments</h1>
          <p className="text-muted-foreground">Track and compare LLM runs</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
          <Plus className="w-4 h-4" />
          New Experiment
        </button>
      </div>

      <GlassCard>
        <div className="flex items-center gap-4 mb-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search experiments..."
              className="pl-9 pr-4 py-2 rounded-lg bg-background/50 border border-border/50 text-sm w-full"
            />
          </div>
          <button className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
            <Filter className="w-4 h-4" />
            Filter
          </button>
        </div>

        <div className="space-y-2">
          {[
            { name: "GPT-4o vs Claude Opus - Math", runs: 24, status: "complete", score: 0.87 },
            { name: "Prompt Template A/B Test", runs: 48, status: "running", score: null },
            { name: "Cost Optimization Trial", runs: 12, status: "complete", score: 0.92 },
          ].map((exp, i) => (
            <div
              key={i}
              className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:bg-accent/50 transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <FlaskConical className="w-4 h-4 text-purple-500" />
                </div>
                <div>
                  <p className="font-medium">{exp.name}</p>
                  <p className="text-xs text-muted-foreground">{exp.runs} runs</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                {exp.score !== null && (
                  <span className="text-sm font-medium">Score: {exp.score}</span>
                )}
                <span className={`px-2 py-0.5 rounded-full text-xs ${
                  exp.status === "complete"
                    ? "bg-green-500/10 text-green-500"
                    : "bg-yellow-500/10 text-yellow-500"
                }`}>
                  {exp.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}
