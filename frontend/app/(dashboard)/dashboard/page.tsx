"use client";

import { useDashboardSummary } from "@/hooks/use-api";
import { KpiCard, GlassCard, LoadingPage } from "@/components/ui/cards";
import { formatCurrency, formatLatency, formatNumber } from "@/lib/utils";
import {
  Activity,
  DollarSign,
  Clock,
  CheckCircle,
  AlertTriangle,
  Zap,
  Server,
  Cpu,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";

export default function DashboardPage() {
  const { data: summary, isLoading } = useDashboardSummary();

  if (isLoading) return <LoadingPage />;

  const s = summary || {};

  return (
    <div className="page-container">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">Real-time overview of your LLM infrastructure</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          Live
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Requests Today"
          value={s.requests_today || 0}
          format="number"
          icon={<Activity className="w-5 h-5" />}
          trend={12.5}
        />
        <KpiCard
          title="Cost Today"
          value={s.cost_today_usd || 0}
          format="currency"
          icon={<DollarSign className="w-5 h-5" />}
          trend={-3.2}
        />
        <KpiCard
          title="Avg Latency"
          value={s.avg_latency_ms || 0}
          format="latency"
          icon={<Clock className="w-5 h-5" />}
          trend={-8.1}
        />
        <KpiCard
          title="Success Rate"
          value={s.success_rate_pct || 0}
          format="percent"
          icon={<CheckCircle className="w-5 h-5" />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassCard title="Requests" className="lg:col-span-2" description="Requests over the last 24 hours">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={[]}>
                <defs>
                  <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(217, 91%, 60%)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(217, 91%, 60%)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="requests"
                  stroke="hsl(217, 91%, 60%)"
                  fillOpacity={1}
                  fill="url(#colorRequests)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard title="GPU Utilization">
          <div className="space-y-4">
            <div className="text-center">
              <p className="text-4xl font-bold text-primary">{s.gpu_util_pct_avg || 0}%</p>
              <p className="text-sm text-muted-foreground mt-1">Average GPU Usage</p>
            </div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={[]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                  <Bar dataKey="util" fill="hsl(217, 91%, 60%)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassCard title="Model Usage" description="Top models by request count">
          <div className="space-y-3">
            {(s.model_usage || []).slice(0, 5).map((m: any, i: number) => (
              <div key={i} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-xs font-medium">
                    {i + 1}
                  </div>
                  <div>
                    <p className="text-sm font-medium">{m.model_id}</p>
                    <p className="text-xs text-muted-foreground">{formatCurrency(m.cost_usd)} spent</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium">{formatNumber(m.request_count)}</p>
                  <p className="text-xs text-muted-foreground">requests</p>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard title="Provider Usage" description="Requests by provider">
          <div className="space-y-3">
            {(s.provider_usage || []).slice(0, 5).map((p: any, i: number) => (
              <div key={i} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
                    <Server className="w-4 h-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium capitalize">{p.provider_type}</p>
                    <p className="text-xs text-muted-foreground">{formatCurrency(p.cost_usd)} spent</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium">{formatNumber(p.request_count)}</p>
                  <p className="text-xs text-muted-foreground">requests</p>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-500/10">
              <CheckCircle className="w-5 h-5 text-green-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Active Deployments</p>
              <p className="text-xl font-bold">{s.active_deployments || 0}</p>
            </div>
          </div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/10">
              <Zap className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Tokens Used</p>
              <p className="text-xl font-bold">{formatNumber(s.tokens_used_today || 0)}</p>
            </div>
          </div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-yellow-500/10">
              <AlertTriangle className="w-5 h-5 text-yellow-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Error Rate</p>
              <p className="text-xl font-bold">{(s.error_rate_pct || 0).toFixed(1)}%</p>
            </div>
          </div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/10">
              <Cpu className="w-5 h-5 text-purple-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Req/min</p>
              <p className="text-xl font-bold">{(s.requests_per_minute || 0).toFixed(1)}</p>
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
