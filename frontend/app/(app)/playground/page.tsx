"use client";

import { useState } from "react";
import { GlassCard } from "@/components/ui/cards";
import { Play, Plus, ThumbsUp, ThumbsDown } from "lucide-react";

export default function PlaygroundPage() {
  const [prompt, setPrompt] = useState("");
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [results, setResults] = useState<any[]>([]);

  return (
    <div className="page-container">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Playground</h1>
        <p className="text-muted-foreground">Compare model outputs side by side</p>
      </div>

      <GlassCard>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Prompt</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter your prompt here..."
              className="w-full h-32 px-4 py-3 rounded-lg bg-background/50 border border-border/50 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-2 block">Models</label>
            <div className="flex flex-wrap gap-2">
              {["gpt-4o", "claude-opus-5", "gemini-pro", "llama3.1-8b"].map((model) => (
                <button
                  key={model}
                  onClick={() => setSelectedModels((prev) => prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model])}
                  className={`px-3 py-1.5 rounded-lg text-sm border transition-colors ${selectedModels.includes(model) ? "bg-primary/10 border-primary/30 text-primary" : "border-border/50 hover:bg-accent"}`}
                >
                  {model}
                </button>
              ))}
              <button className="px-3 py-1.5 rounded-lg text-sm border border-dashed border-border/50 hover:bg-accent transition-colors">
                <Plus className="w-3 h-3 inline mr-1" /> Custom
              </button>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button disabled={!prompt || selectedModels.length === 0} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
              <Play className="w-4 h-4" /> Run Comparison
            </button>
          </div>
        </div>
      </GlassCard>

      {results.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {results.map((r, i) => (
            <GlassCard key={i}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold">{r.model}</h3>
                <div className="flex gap-1">
                  <button className="p-1 rounded hover:bg-green-500/10 hover:text-green-500 transition-colors"><ThumbsUp className="w-4 h-4" /></button>
                  <button className="p-1 rounded hover:bg-red-500/10 hover:text-red-500 transition-colors"><ThumbsDown className="w-4 h-4" /></button>
                </div>
              </div>
              <p className="text-sm whitespace-pre-wrap">{r.response}</p>
              <div className="mt-4 pt-3 border-t border-border/50 grid grid-cols-3 gap-2 text-center text-sm">
                <div><p className="font-medium">{r.latency_ms}ms</p><p className="text-xs text-muted-foreground">Latency</p></div>
                <div><p className="font-medium">${r.cost_usd?.toFixed(4)}</p><p className="text-xs text-muted-foreground">Cost</p></div>
                <div><p className="font-medium">{r.tokens}</p><p className="text-xs text-muted-foreground">Tokens</p></div>
              </div>
            </GlassCard>
          ))}
        </div>
      )}
    </div>
  );
}
