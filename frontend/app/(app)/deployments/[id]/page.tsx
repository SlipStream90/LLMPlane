"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  useDeployment,
  useDeploymentAction,
  useDeleteDeployment,
  useDeploymentTelemetry,
  useDeploymentLiveSync,
} from "@/hooks/useDeployments";
import {
  PageHeader,
  Panel,
  StatusBadge,
  LoadingPage,
  EmptyState,
  KpiCard,
} from "@/components/ui/cards";
import { DeploymentLogs } from "@/components/deployment/DeploymentLogs";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { cn } from "@/lib/utils";
import { ArrowLeft, Play, Square, RotateCw, Trash2, Container } from "lucide-react";

export default function DeploymentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: deployment, isLoading } = useDeployment(id);
  const { data: telemetry } = useDeploymentTelemetry(id);
  const action = useDeploymentAction();
  const remove = useDeleteDeployment();
  const [confirmDelete, setConfirmDelete] = useState(false);

  useDeploymentLiveSync();

  if (isLoading) return <LoadingPage />;

  if (!deployment) {
    return (
      <div className="page-container">
        <BackLink />
        <EmptyState
          icon={<Container className="w-5 h-5" />}
          title="Deployment not found"
          description="It may have been deleted, or it belongs to a different project."
        />
      </div>
    );
  }

  const latest = telemetry?.[0];
  const running = deployment.status === "running";
  const stopped = deployment.status === "stopped" || deployment.status === "error";

  return (
    <div className="page-container">
      <BackLink />

      <PageHeader
        title={deployment.model_ref}
        description={`${deployment.backend_type.toUpperCase()} · created ${new Date(
          deployment.created_at
        ).toLocaleString()}`}
        actions={
          <div className="flex items-center gap-2">
            {stopped && (
              <Btn
                onClick={() => action.mutate({ id, action: "start" })}
                disabled={action.isPending}
                className="bg-success-subtle text-success"
              >
                <Play className="w-3.5 h-3.5" /> Start
              </Btn>
            )}
            {running && (
              <>
                <Btn
                  onClick={() => action.mutate({ id, action: "stop" })}
                  disabled={action.isPending}
                  className="bg-warning-subtle text-warning"
                >
                  <Square className="w-3.5 h-3.5" /> Stop
                </Btn>
                <Btn
                  onClick={() => action.mutate({ id, action: "restart" })}
                  disabled={action.isPending}
                  className="border border-border text-muted-foreground hover:text-foreground"
                >
                  <RotateCw className="w-3.5 h-3.5" /> Restart
                </Btn>
              </>
            )}
            <Btn
              onClick={() => setConfirmDelete(true)}
              className="border border-border text-muted-foreground hover:text-danger hover:border-danger/30"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </Btn>
          </div>
        }
      >
        <div className="mt-3">
          <StatusBadge status={deployment.status} />
        </div>
      </PageHeader>

      {deployment.error_message && (
        <div className="surface border-danger/25 bg-danger-subtle p-4">
          <p className="text-sm font-medium text-danger">Last error</p>
          <p className="text-xs font-mono text-danger mt-1.5 break-words">
            {deployment.error_message}
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title="Port" value={deployment.port ?? null} emptyLabel="Not bound" />
        <KpiCard title="GPU index" value={deployment.gpu_index ?? null} emptyLabel="CPU only" />
        <KpiCard
          title="GPU utilisation"
          value={latest ? latest.gpu_util_pct : null}
          format="percent"
          emptyLabel="No samples"
          hint={latest ? `sampled ${new Date(latest.sampled_at).toLocaleTimeString()}` : undefined}
        />
        <KpiCard
          title="VRAM used"
          value={latest ? `${(latest.vram_used_mb / 1024).toFixed(1)} GB` : null}
          emptyLabel="No samples"
          hint={latest ? `of ${(latest.vram_total_mb / 1024).toFixed(0)} GB` : undefined}
        />
      </div>

      <DeploymentLogs deploymentId={id} />

      <Panel title="Container" description="Runtime identity and configuration.">
        <dl className="grid sm:grid-cols-2 gap-x-8 gap-y-3 text-sm">
          <Row label="Container ID" value={deployment.container_id ?? "—"} mono />
          <Row label="Deployment ID" value={deployment.id} mono />
          <Row label="Provider ID" value={deployment.provider_id} mono />
          <Row label="Backend" value={deployment.backend_type} />
          {Object.entries(deployment.config ?? {}).map(([k, v]) => (
            <Row key={k} label={k.replace(/_/g, " ")} value={String(v)} />
          ))}
        </dl>
      </Panel>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this deployment?"
        description={`The ${deployment.backend_type} container running ${deployment.model_ref} will be stopped and removed. This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={() => {
          remove.mutate({ id });
          setConfirmDelete(false);
        }}
      />
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/deployments"
      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
    >
      <ArrowLeft className="w-3.5 h-3.5" /> All deployments
    </Link>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border pb-2 last:border-0">
      <dt className="text-muted-foreground capitalize shrink-0">{label}</dt>
      <dd className={cn("truncate text-right", mono && "font-mono text-xs")} title={value}>
        {value}
      </dd>
    </div>
  );
}

function Btn({
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all disabled:opacity-50 disabled:pointer-events-none hover:brightness-110",
        className
      )}
    >
      {children}
    </button>
  );
}
