/**
 * Single source of truth for status semantics.
 *
 * Status colours were previously re-declared in at least five places
 * (`ui/cards.tsx`, `command-center/node-state.ts`, `command-center/InfraNodeMesh.tsx`,
 * `benchmarks/page.tsx`, `logs/page.tsx`), each with slightly different mappings
 * and all using raw Tailwind palette classes (`bg-green-500/10`) rather than the
 * design tokens. That drift is why the same state rendered in different colours
 * on different pages — and why the command center's demo "warning" provider fell
 * through to grey, since only `healthy`/`degraded`/`down` were mapped there.
 *
 * Every status string the backend can emit is mapped here explicitly. Unknown
 * values fall back to `neutral` rather than silently reading as an error.
 */

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

/** Backend status vocabularies, from `backend/app/models/enums.py`. */
const TONE_BY_STATUS: Record<string, Tone> = {
  // HealthStatus
  healthy: "success",
  degraded: "warning",
  down: "danger",
  unknown: "neutral",

  // DeploymentStatus
  running: "success",
  pending: "warning",
  downloading: "info",
  stopped: "neutral",
  error: "danger",

  // RunStatus / ItemStatus. The backend enum value is `complete`, but the
  // Experiment type declares `completed` and the API has been observed to emit
  // it — both are mapped rather than making call sites normalize, which is how
  // finished experiments were rendering grey instead of green.
  complete: "success",
  completed: "success",
  failed: "danger",

  // RequestStatus
  success: "success",
  timeout: "warning",

  // Generic UI states
  active: "success",
  inactive: "neutral",
  warning: "warning",
  stopping: "warning",
  starting: "info",
};

export function toneFor(status: string | null | undefined): Tone {
  if (!status) return "neutral";
  return TONE_BY_STATUS[status.toLowerCase()] ?? "neutral";
}

/**
 * Token-backed classes per tone. `text-*`/`bg-*` here resolve through the
 * `@theme inline` mapping in globals.css, so they follow the active theme
 * instead of being pinned to a dark-only palette value.
 */
export const TONE_CLASSES: Record<Tone, { text: string; bg: string; border: string; dot: string }> = {
  success: {
    text: "text-success",
    bg: "bg-success-subtle",
    border: "border-success/25",
    dot: "bg-success",
  },
  warning: {
    text: "text-warning",
    bg: "bg-warning-subtle",
    border: "border-warning/25",
    dot: "bg-warning",
  },
  danger: {
    text: "text-danger",
    bg: "bg-danger-subtle",
    border: "border-danger/25",
    dot: "bg-danger",
  },
  info: {
    text: "text-info",
    bg: "bg-info-subtle",
    border: "border-info/25",
    dot: "bg-info",
  },
  neutral: {
    text: "text-muted-foreground",
    bg: "bg-surface-2",
    border: "border-border",
    dot: "bg-subtle-foreground",
  },
};

/** Statuses that represent work in flight — used to drive pulse affordances. */
const TRANSIENT = new Set(["pending", "downloading", "starting", "stopping", "running_item"]);

export function isTransient(status: string | null | undefined): boolean {
  return !!status && TRANSIENT.has(status.toLowerCase());
}

/** Hex values for canvas/SVG contexts that cannot consume CSS classes. */
export const TONE_HEX: Record<Tone, string> = {
  success: "#3fbf80",
  warning: "#e0a13a",
  danger: "#e5624f",
  info: "#4aa3e8",
  neutral: "#7c8398",
};
