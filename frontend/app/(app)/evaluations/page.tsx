"use client";

import { useEvaluations } from "@/hooks/useEvaluations";
import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Search, Filter, Download } from "lucide-react";

export default function EvaluationsPage() {
  const { data: evaluations, isLoading } = useEvaluations();

  if (isLoading) return <LoadingPage />;

  const list = evaluations || [];

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Evaluations</h1>
          <p className="text-muted-foreground">View evaluation scores across runs</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
          <Download className="w-4 h-4" /> Export
        </button>
      </div>

      <div className="flex items-center gap-4 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input type="text" placeholder="Filter by metric, model, or dataset..." className="pl-9 pr-4 py-2 rounded-lg bg-background/50 border border-border/50 text-sm w-full" />
        </div>
        <button className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
          <Filter className="w-4 h-4" /> Filters
        </button>
      </div>

      <GlassCard>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50">
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Model</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Prompt</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Score</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Metrics</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Date</th>
              </tr>
            </thead>
            <tbody>
              {list.map((row) => (
                <tr key={row.id} className="border-b border-border/30 hover:bg-accent/30 transition-colors">
                  <td className="py-3 px-4 font-medium">{row.model}</td>
                  <td className="py-3 px-4 text-muted-foreground">{row.prompt_name}</td>
                  <td className="py-3 px-4 text-right">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs ${row.score >= 0.9 ? "bg-green-500/10 text-green-500" : row.score >= 0.8 ? "bg-yellow-500/10 text-yellow-500" : "bg-red-500/10 text-red-500"}`}>
                      {row.score.toFixed(2)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right text-xs text-muted-foreground">
                    {Object.entries(row.metrics).map(([k, v]) => `${k}: ${(v as number).toFixed(2)}`).join(", ")}
                  </td>
                  <td className="py-3 px-4 text-right text-muted-foreground">{new Date(row.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
              {list.length === 0 && (
                <tr><td colSpan={5} className="py-12 text-center text-muted-foreground">No evaluations yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
}
