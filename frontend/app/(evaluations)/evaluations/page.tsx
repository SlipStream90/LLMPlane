"use client";

import { GlassCard, LoadingPage } from "@/components/ui/cards";
import { Search, Filter, Download } from "lucide-react";

export default function EvaluationsPage() {
  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Evaluations</h1>
          <p className="text-muted-foreground">View evaluation scores across runs</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
          <Download className="w-4 h-4" />
          Export
        </button>
      </div>

      <div className="flex items-center gap-4 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Filter by metric, model, or dataset..."
            className="pl-9 pr-4 py-2 rounded-lg bg-background/50 border border-border/50 text-sm w-full"
          />
        </div>
        <button className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border/50 text-sm hover:bg-accent transition-colors">
          <Filter className="w-4 h-4" />
          Filters
        </button>
      </div>

      <GlassCard>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border/50">
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Model</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Dataset</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Faithfulness</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Relevance</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Latency</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Cost</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">Judge Score</th>
              </tr>
            </thead>
            <tbody>
              {[
                { model: "gpt-4o", dataset: "math_problems", faithfulness: 0.94, relevance: 0.91, latency: 842, cost: 0.0031, judge: 0.89 },
                { model: "claude-opus-5", dataset: "math_problems", faithfulness: 0.96, relevance: 0.93, latency: 1205, cost: 0.0045, judge: 0.92 },
                { model: "gemini-pro", dataset: "qa_eval", faithfulness: 0.88, relevance: 0.85, latency: 654, cost: 0.0018, judge: 0.84 },
                { model: "llama3.1-8b", dataset: "qa_eval", faithfulness: 0.82, relevance: 0.79, latency: 320, cost: 0.0002, judge: 0.78 },
              ].map((row, i) => (
                <tr key={i} className="border-b border-border/30 hover:bg-accent/30 transition-colors">
                  <td className="py-3 px-4 font-medium">{row.model}</td>
                  <td className="py-3 px-4 text-muted-foreground">{row.dataset}</td>
                  <td className="py-3 px-4 text-right">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs ${
                      row.faithfulness >= 0.9 ? "bg-green-500/10 text-green-500" :
                      row.faithfulness >= 0.8 ? "bg-yellow-500/10 text-yellow-500" :
                      "bg-red-500/10 text-red-500"
                    }`}>
                      {row.faithfulness.toFixed(2)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs ${
                      row.relevance >= 0.9 ? "bg-green-500/10 text-green-500" :
                      row.relevance >= 0.8 ? "bg-yellow-500/10 text-yellow-500" :
                      "bg-red-500/10 text-red-500"
                    }`}>
                      {row.relevance.toFixed(2)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">{row.latency}ms</td>
                  <td className="py-3 px-4 text-right">${row.cost.toFixed(4)}</td>
                  <td className="py-3 px-4 text-right font-medium">{row.judge.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
}
