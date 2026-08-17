import type { NodeState } from "./types";

/**
 * Node state presentation, kept in a dependency-free module.
 *
 * These used to live in `InfraNodeMesh.tsx`, which meant every consumer — the
 * legend, the inspector panel, the 2D canvas — transitively imported
 * `three` / `@react-three/fiber`.
 */
export const STATE_COLORS: Record<NodeState, string> = {
  healthy: "#22c55e",
  "high-load": "#eab308",
  warning: "#f59e0b",
  critical: "#ef4444",
  offline: "#64748b",
};

export const STATE_LABEL: Record<NodeState, string> = {
  healthy: "Healthy",
  "high-load": "High Load",
  warning: "Warning",
  critical: "Critical",
  offline: "Offline",
};
