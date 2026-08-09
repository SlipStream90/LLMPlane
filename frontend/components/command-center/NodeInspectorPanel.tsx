"use client";

import { X } from "lucide-react";
import type { InfraNode } from "./types";
import { STATE_COLORS, STATE_LABEL } from "./InfraNodeMesh";

interface Props {
  node: InfraNode | null;
  onClose: () => void;
}

export function NodeInspectorPanel({ node, onClose }: Props) {
  const open = !!node;
  return (
    <div
      className={`absolute top-0 right-0 h-full w-80 max-w-[85vw] border-l border-border bg-card/95 backdrop-blur-xl shadow-2xl transition-transform duration-300 z-30 ${
        open ? "translate-x-0" : "translate-x-full"
      }`}
      aria-hidden={!open}
    >
      {node && (
        <div className="flex flex-col h-full">
          <div className="flex items-start justify-between p-4 border-b border-border">
            <div>
              <p className="text-xs uppercase tracking-wider text-muted-foreground">
                {node.kind}
              </p>
              <h2 className="text-lg font-semibold">{node.label}</h2>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md hover:bg-muted transition-colors"
              aria-label="Close panel"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="p-4 space-y-4 overflow-y-auto flex-1">
            <div className="flex items-center gap-2">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{
                  backgroundColor: STATE_COLORS[node.state],
                  boxShadow: `0 0 10px ${STATE_COLORS[node.state]}`,
                }}
              />
              <span
                className="text-sm font-medium"
                style={{ color: STATE_COLORS[node.state] }}
              >
                {STATE_LABEL[node.state]}
              </span>
            </div>

            {Object.keys(node.metrics).length > 0 && (
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                  Metrics
                </p>
                <dl className="space-y-1.5">
                  {Object.entries(node.metrics).map(([k, v]) => (
                    <div
                      key={k}
                      className="flex items-center justify-between text-sm"
                    >
                      <dt className="text-muted-foreground">{k}</dt>
                      <dd className="font-mono">{String(v)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            )}

            {node.providerType && (
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                  Type
                </p>
                <p className="text-sm font-mono">{node.providerType}</p>
              </div>
            )}

            {node.source && (
              <div>
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
                  Source
                </p>
                <pre className="text-[11px] bg-muted/50 rounded-md p-3 overflow-auto max-h-48 text-muted-foreground">
                  {JSON.stringify(node.source.raw, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
