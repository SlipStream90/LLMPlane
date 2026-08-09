"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateDeployment, useDeploymentBackends } from "@/hooks/useDeployments";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/cards";
import { cn } from "@/lib/utils";
import {
  Cpu,
  Boxes,
  SlidersHorizontal,
  Network,
  HeartPulse,
  Rocket,
  Check,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";

interface WizardConfig {
  context_length: string;
  batch_size: string;
  quantization: string;
  tensor_parallelism: string;
  gpu_memory_utilization: string;
  protocol: string;
  authentication: boolean;
  health_liveness: string;
  health_readiness: string;
  health_startup: string;
}

const EMPTY_CONFIG: WizardConfig = {
  context_length: "4096",
  batch_size: "32",
  quantization: "none",
  tensor_parallelism: "1",
  gpu_memory_utilization: "0.9",
  protocol: "http",
  authentication: false,
  health_liveness: "/health",
  health_readiness: "/health/ready",
  health_startup: "/health",
};

const STEPS = [
  { title: "Select Model", icon: Cpu },
  { title: "Select Runtime", icon: Boxes },
  { title: "Hardware", icon: Cpu },
  { title: "Configuration", icon: SlidersHorizontal },
  { title: "Networking", icon: Network },
  { title: "Health Checks", icon: HeartPulse },
  { title: "Deploy", icon: Rocket },
];

export function DeploymentWizard() {
  const router = useRouter();
  const createDeployment = useCreateDeployment();
  const { data: backends } = useDeploymentBackends();

  const [step, setStep] = useState(0);
  const [modelRef, setModelRef] = useState("");
  const [backendType, setBackendType] = useState<"ollama" | "vllm" | "">("");
  const [gpuIndex, setGpuIndex] = useState<string>("0");
  const [config, setConfig] = useState<WizardConfig>(EMPTY_CONFIG);
  const [deploying, setDeploying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const gpuAvailable = backends?.gpu_available ?? false;
  const set = <K extends keyof WizardConfig>(k: K, v: WizardConfig[K]) =>
    setConfig((c) => ({ ...c, [k]: v }));

  const canAdvance = (() => {
    if (step === 0) return modelRef.trim().length > 0;
    if (step === 1) return backendType !== "";
    return true;
  })();

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  const deploy = async () => {
    setDeploying(true);
    setError(null);
    try {
      await createDeployment.mutateAsync({
        backend_type: backendType as "ollama" | "vllm",
        model_ref: modelRef.trim(),
        gpu_index: backendType === "vllm" ? Number(gpuIndex) : null,
        config: {
          ...config,
          gpu_index: backendType === "vllm" ? Number(gpuIndex) : null,
        },
      });
      router.push("/deployments");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Deployment failed.");
      setDeploying(false);
    }
  };

  return (
    <div className="page-container max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">New Deployment</h1>
          <p className="text-muted-foreground">Launch a local model with the wizard</p>
        </div>
        <Button variant="ghost" onClick={() => router.push("/deployments")}>
          Cancel
        </Button>
      </div>

      {/* Stepper */}
      <div className="flex items-center mb-6 overflow-x-auto">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const active = i === step;
          const done = i < step;
          return (
            <div key={s.title} className="flex items-center">
              <div className="flex flex-col items-center gap-1 shrink-0">
                <div
                  className={cn(
                    "w-9 h-9 rounded-full flex items-center justify-center border transition-colors",
                    active
                      ? "bg-primary text-primary-foreground border-primary"
                      : done
                      ? "bg-primary/15 text-primary border-primary/40"
                      : "bg-muted text-muted-foreground border-border"
                  )}
                >
                  {done ? <Check className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                </div>
                <span className={cn("text-[10px] whitespace-nowrap", active ? "text-foreground" : "text-muted-foreground")}>
                  {s.title}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={cn("w-10 h-px mx-1", done ? "bg-primary/40" : "bg-border")} />
              )}
            </div>
          );
        })}
      </div>

      <GlassCard>
        {/* Step 1: Model */}
        {step === 0 && (
          <div className="space-y-4">
            <label className="text-sm font-medium block">Model reference</label>
            <input
              value={modelRef}
              onChange={(e) => setModelRef(e.target.value)}
              placeholder="e.g. llama3.1:8b  ·  Qwen/Qwen2.5-7B-Instruct"
              className="w-full px-4 py-2.5 rounded-lg bg-background/50 border border-border/50 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
            <p className="text-xs text-muted-foreground">
              An Ollama tag or Hugging Face model id, passed as an argument to an
              allow-listed image.
            </p>
          </div>
        )}

        {/* Step 2: Runtime */}
        {step === 1 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { id: "ollama", label: "Ollama", desc: "CPU/GPU friendly · 11434", gpu: false },
              { id: "vllm", label: "vLLM", desc: "High-throughput · requires GPU", gpu: true },
            ].map((b) => {
              const disabled = b.gpu && !gpuAvailable;
              return (
                <button
                  key={b.id}
                  disabled={disabled}
                  onClick={() => setBackendType(b.id as "ollama" | "vllm")}
                  className={cn(
                    "text-left p-4 rounded-lg border transition-colors",
                    backendType === b.id
                      ? "border-primary/50 bg-primary/5"
                      : "border-border/50 hover:bg-accent/30",
                    disabled && "opacity-40 cursor-not-allowed"
                  )}
                >
                  <p className="font-medium capitalize">{b.label}</p>
                  <p className="text-xs text-muted-foreground mt-1">{b.desc}</p>
                  {disabled && <p className="text-xs text-red-400 mt-1">No GPU detected</p>}
                </button>
              );
            })}
          </div>
        )}

        {/* Step 3: Hardware */}
        {step === 2 && (
          <div className="grid grid-cols-2 gap-4">
            <Field label="GPU Index" hint="Used for vLLM deployments">
              <input
                type="number"
                min={0}
                value={gpuIndex}
                onChange={(e) => setGpuIndex(e.target.value)}
                disabled={backendType !== "vllm"}
                className="w-full px-3 py-2 rounded-lg bg-background/50 border border-border/50 text-sm disabled:opacity-50"
              />
            </Field>
            <Field label="CPU Cores" hint="Allocated to the container">
              <input
                value={(config as any).cpu_cores ?? "8"}
                onChange={(e) => set("tensor_parallelism", e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-background/50 border border-border/50 text-sm"
              />
            </Field>
          </div>
        )}

        {/* Step 4: Configuration */}
        {step === 3 && (
          <div className="grid grid-cols-2 gap-4">
            <Field label="Context Length"><input value={config.context_length} onChange={(e) => set("context_length", e.target.value)} className={inputCls} /></Field>
            <Field label="Batch Size"><input value={config.batch_size} onChange={(e) => set("batch_size", e.target.value)} className={inputCls} /></Field>
            <Field label="Quantization">
              <select value={config.quantization} onChange={(e) => set("quantization", e.target.value)} className={inputCls}>
                {["none", "fp8", "int8", "int4", "awq", "gptq"].map((q) => (
                  <option key={q} value={q}>{q}</option>
                ))}
              </select>
            </Field>
            <Field label="Tensor Parallelism"><input value={config.tensor_parallelism} onChange={(e) => set("tensor_parallelism", e.target.value)} className={inputCls} /></Field>
            <Field label="GPU Memory Utilization"><input value={config.gpu_memory_utilization} onChange={(e) => set("gpu_memory_utilization", e.target.value)} className={inputCls} /></Field>
          </div>
        )}

        {/* Step 5: Networking */}
        {step === 4 && (
          <div className="grid grid-cols-2 gap-4">
            <Field label="Protocol">
              <select value={config.protocol} onChange={(e) => set("protocol", e.target.value)} className={inputCls}>
                {["http", "https", "grpc"].map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </Field>
            <Field label="Authentication">
              <button
                onClick={() => set("authentication", !config.authentication)}
                className={cn("w-full px-3 py-2 rounded-lg border text-sm", config.authentication ? "bg-primary/10 border-primary/40 text-primary" : "bg-background/50 border-border/50")}
              >
                {config.authentication ? "Required" : "None"}
              </button>
            </Field>
          </div>
        )}

        {/* Step 6: Health Checks */}
        {step === 5 && (
          <div className="grid grid-cols-1 gap-4">
            <Field label="Liveness Path"><input value={config.health_liveness} onChange={(e) => set("health_liveness", e.target.value)} className={inputCls} /></Field>
            <Field label="Readiness Path"><input value={config.health_readiness} onChange={(e) => set("health_readiness", e.target.value)} className={inputCls} /></Field>
            <Field label="Startup Path"><input value={config.health_startup} onChange={(e) => set("health_startup", e.target.value)} className={inputCls} /></Field>
          </div>
        )}

        {/* Step 7: Deploy */}
        {step === 6 && (
          <div className="space-y-4">
            <div className="rounded-lg bg-background/50 p-4 text-sm space-y-1.5">
              <Row k="Model" v={modelRef} />
              <Row k="Runtime" v={backendType} />
              <Row k="GPU" v={backendType === "vllm" ? `#${gpuIndex}` : "n/a"} />
              <Row k="Context" v={config.context_length} />
              <Row k="Quantization" v={config.quantization} />
              <Row k="Protocol" v={config.protocol} />
            </div>
            {deploying ? (
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Rocket className="w-4 h-4 animate-pulse text-primary" />
                Submitting deployment to the worker…
              </div>
            ) : (
              <button
                onClick={deploy}
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Rocket className="w-4 h-4" /> Deploy {modelRef}
              </button>
            )}
            {error && <p className="text-sm text-red-400 font-mono">{error}</p>}
          </div>
        )}

        {/* Nav */}
        {step !== 6 && (
          <div className="flex items-center justify-between mt-6">
            <Button variant="ghost" onClick={back} disabled={step === 0}>
              <ArrowLeft className="w-4 h-4" /> Back
            </Button>
            <Button onClick={next} disabled={!canAdvance}>
              Next <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        )}
        {step === 6 && !deploying && (
          <div className="flex items-center justify-between mt-6">
            <Button variant="ghost" onClick={back}>
              <ArrowLeft className="w-4 h-4" /> Back
            </Button>
            <Button variant="ghost" onClick={() => router.push("/deployments")}>
              Cancel
            </Button>
          </div>
        )}
      </GlassCard>
    </div>
  );
}

const inputCls =
  "w-full px-3 py-2 rounded-lg bg-background/50 border border-border/50 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50";

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-sm font-medium block mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground mt-1">{hint}</p>}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-mono">{v || "—"}</span>
    </div>
  );
}
