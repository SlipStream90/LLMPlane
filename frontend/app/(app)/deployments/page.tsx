"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useDeployments,
  useDeploymentAction,
  useDeleteDeployment,
  useDeploymentLiveSync,
  type Deployment,
} from "@/hooks/useDeployments";
import {
  PageHeader,
  StatusBadge,
  LoadingPage,
  EmptyState,
  ErrorState,
} from "@/components/ui/cards";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { cn } from "@/lib/utils";
import {
  Play,
  Square,
  RotateCw,
  Trash2,
  Plus,
  Container,
  ScrollText,
  ChevronRight,
} from "lucide-react";

export default function DeploymentsPage() {
  const router = useRouter();
  const { data: deployments, isLoading, isError, error, refetch } = useDeployments();
  const action = useDeploymentAction();
  const remove = useDeleteDeployment();
  const [pendingDelete, setPendingDelete] = useState<Deployment | null>(null);

  // Status transitions are made by the Celery worker, not by the mutation
  // response — this keeps the list honest as containers actually change state.
  useDeploymentLiveSync();

  if (isLoading) return <LoadingPage />;

  const list = deployments ?? [];

  return (
    <div className="page-container">
      <PageHeader
        title="Deployments"
        description="Self-hosted models running as containers on your infrastructure."
        actions={
          <button
            onClick={() => router.push("/deployments/new")}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary-hover transition-colors"
          >
            <Plus className="w-4 h-4" /> New deployment
          </button>
        }
      />

      {isError && <ErrorState title="Could not load deployments" error={error} onRetry={refetch} />}

      <StalledNotice deployments={list} />

      {!isError && list.length === 0 && (
        <EmptyState
          icon={<Container className="w-5 h-5" />}
          title="No deployments yet"
          description="Deploy a model with Ollama or vLLM and it will appear here with live status, logs and GPU telemetry."
          action={
            <button
              onClick={() => router.push("/deployments/new")}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary-hover transition-colors"
            >
              <Plus className="w-4 h-4" /> Deploy your first model
            </button>
          }
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {list.map((d) => (
          <article key={d.id} className="surface surface-interactive p-5 flex flex-col">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <Link
                  href={`/deployments/${d.id}`}
                  className="font-medium font-mono text-sm truncate hover:text-primary transition-colors flex items-center gap-1 group"
                >
                  <span className="truncate">{d.model_ref}</span>
                  <ChevronRight className="w-3.5 h-3.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
                <p className="text-xs text-muted-foreground mt-1 uppercase tracking-wide">
                  {d.backend_type}
                </p>
              </div>
              <StatusBadge status={d.status} />
            </div>

            {d.status === "downloading" && (
              <div className="mt-4">
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
                  <span>Pulling weights</span>
                  <span className="tabular">
                    {d.download_progress_pct != null ? `${d.download_progress_pct}%` : "…"}
                  </span>
                </div>
                <div className="h-1 rounded-full bg-surface-3 overflow-hidden">
                  <div
                    className={cn(
                      "h-full bg-primary transition-all duration-500",
                      d.download_progress_pct == null && "w-1/3 animate-pulse"
                    )}
                    style={
                      d.download_progress_pct != null
                        ? { width: `${d.download_progress_pct}%` }
                        : undefined
                    }
                  />
                </div>
              </div>
            )}

            <dl className="mt-4 grid grid-cols-3 gap-px rounded-md overflow-hidden bg-border">
              <Stat label="GPU" value={d.gpu_index ?? "—"} />
              <Stat label="Port" value={d.port ?? "—"} />
              <Stat label="Quant" value={String(d.config?.quantization ?? "—")} />
            </dl>

            {d.error_message && (
              <p className="mt-3 text-xs text-danger font-mono break-words line-clamp-3">
                {d.error_message}
              </p>
            )}

            <div className="mt-4 pt-4 border-t border-border flex items-center gap-2">
              {d.status === "stopped" || d.status === "error" ? (
                <ActionButton
                  tone="success"
                  icon={<Play className="w-3.5 h-3.5" />}
                  label="Start"
                  busy={action.isPending}
                  onClick={() => action.mutate({ id: d.id, action: "start" })}
                />
              ) : d.status === "running" ? (
                <>
                  <ActionButton
                    tone="warning"
                    icon={<Square className="w-3.5 h-3.5" />}
                    label="Stop"
                    busy={action.isPending}
                    onClick={() => action.mutate({ id: d.id, action: "stop" })}
                  />
                  <ActionButton
                    tone="neutral"
                    icon={<RotateCw className="w-3.5 h-3.5" />}
                    label="Restart"
                    busy={action.isPending}
                    onClick={() => action.mutate({ id: d.id, action: "restart" })}
                  />
                </>
              ) : (
                <span className="flex-1 text-center px-3 py-1.5 rounded-md border border-border text-sm text-muted-foreground capitalize">
                  {d.status}…
                </span>
              )}

              <Link
                href={`/deployments/${d.id}`}
                title="View logs"
                aria-label="View logs"
                className="p-2 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
              >
                <ScrollText className="w-3.5 h-3.5" />
              </Link>

              <button
                onClick={() => setPendingDelete(d)}
                title="Delete deployment"
                aria-label="Delete deployment"
                className="p-2 rounded-md border border-border text-muted-foreground hover:text-danger hover:border-danger/30 hover:bg-danger-subtle transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </article>
        ))}
      </div>

      {/* Deleting a container was previously a single unguarded click. */}
      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title="Delete this deployment?"
        description={
          pendingDelete
            ? `The ${pendingDelete.backend_type} container running ${pendingDelete.model_ref} will be stopped and removed. This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        onConfirm={() => {
          if (pendingDelete) remove.mutate({ id: pendingDelete.id });
          setPendingDelete(null);
        }}
      />
    </div>
  );
}

const STALL_THRESHOLD_MS = 5 * 60_000;

/**
 * Creating a deployment writes a `pending` row and enqueues a Celery task; the
 * container is launched by a *worker*, in a separate process. If no worker is
 * consuming the queue the API still returns 202 and the row simply never
 * advances — which looks identical to "still starting" from here.
 *
 * The cloud compose profile (`docker/docker-compose.cloud.yml`) tags `workers`,
 * `scheduler` and `docker-socket-proxy` as `local-only`, so this is the
 * expected state on a hosted deploy rather than a rare failure. We can only
 * infer it, so the wording is explicitly a suggestion, not a diagnosis.
 */
function StalledNotice({ deployments }: { deployments: Deployment[] }) {
  const stalled = deployments.filter(
    (d) =>
      d.status === "pending" &&
      Date.now() - new Date(d.created_at).getTime() > STALL_THRESHOLD_MS
  );
  if (stalled.length === 0) return null;

  return (
    <div className="surface border-warning/25 bg-warning-subtle p-4">
      <p className="text-sm font-medium text-warning">
        {stalled.length} deployment{stalled.length > 1 ? "s have" : " has"} been pending for
        over five minutes
      </p>
      <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed">
        Containers are launched by the Celery worker, not by the API. A row that never leaves{" "}
        <span className="font-mono text-xs">pending</span> usually means no worker is consuming
        the queue — the worker, scheduler and Docker socket proxy only run under the{" "}
        <span className="font-mono text-xs">local-only</span> compose profile, so they are absent
        on a hosted deployment.
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-surface-2 px-3 py-2.5 text-center">
      <dd className="text-sm font-medium tabular truncate">{value}</dd>
      <dt className="text-[0.6875rem] text-subtle-foreground mt-0.5 uppercase tracking-wide">
        {label}
      </dt>
    </div>
  );
}

function ActionButton({
  tone,
  icon,
  label,
  onClick,
  busy,
}: {
  tone: "success" | "warning" | "neutral";
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  busy?: boolean;
}) {
  const tones = {
    success: "bg-success-subtle text-success hover:brightness-110",
    warning: "bg-warning-subtle text-warning hover:brightness-110",
    neutral: "border border-border text-muted-foreground hover:bg-surface-2 hover:text-foreground",
  };
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className={cn(
        "flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all disabled:opacity-50 disabled:pointer-events-none",
        tones[tone]
      )}
    >
      {icon}
      {label}
    </button>
  );
}
