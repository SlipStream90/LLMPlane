"use client";

import { useExperiments } from "@/hooks/useExperiments";
import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Plus, FlaskConical, Search, Filter } from "lucide-react";

export default function ExperimentsPage() {
  const { data: experiments, isLoading } = useExperiments();

  if (isLoading) return <LoadingPage />;

  const list = experiments || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Experiments</h1>
          <p className="text-muted-foreground">Track and compare LLM runs</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
          <Plus className="w-4 h-4" /> New Experiment
        </button>
      </div>

      <GlassCard>
        <div className="flex items-center gap-4 mb-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input type="text" placeholder="Search experiments..." className="pl-9 pr-4 py-2 rounded-lg bg-background/50 border border-border/50 text-sm w-full" />
          </div>
          <button className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
            <Filter className="w-4 h-4" /> Filter
          </button>
        </div>
        <div className="space-y-2">
          {list.map((exp) => (
            <div key={exp.id} className="flex items-center justify-between p-4 rounded-lg border border-border/50 hover:bg-accent/50 transition-colors cursor-pointer">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                  <FlaskConical className="w-4 h-4 text-purple-500" />
                </div>
                <div>
                  <p className="font-medium">{exp.name}</p>
                  <p className="text-xs text-muted-foreground">{exp.runs_count} runs</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className={`px-2 py-0.5 rounded-full text-xs ${exp.status === "completed" ? "bg-green-500/10 text-green-500" : exp.status === "running" ? "bg-yellow-500/10 text-yellow-500" : "bg-muted text-muted-foreground"}`}>
                  {exp.status}
                </span>
              </div>
            </div>
          ))}
          {list.length === 0 && <div className="text-center py-12 text-muted-foreground">No experiments yet.</div>}
        </div>
      </GlassCard>
    </div>
  );
}
