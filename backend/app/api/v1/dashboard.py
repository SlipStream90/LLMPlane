"""Dashboard aggregation API (T031).

Read-only. Everything here is a Postgres aggregate over `request` plus the
latest deployment/GPU state — deliberately not a Prometheus round-trip, because
this is the page users load most and it should not pay an extra network hop
(api-contracts.md 3). Prometheus/Grafana remain the source for infra panels.

These numbers are eventually consistent with gateway traffic (ADR-004).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.api.deps import ProjectDep, SessionDep
from app.repositories.deployment import DeploymentRepository, GpuSampleRepository
from app.repositories.request import RequestRepository
from app.schemas.analytics import (
    DashboardSummary,
    ErrorReason,
    ModelUsage,
    ProviderUsage,
    TimeseriesPoint,
    TimeseriesResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary", response_model=DashboardSummary, summary="Dashboard KPI summary"
)
async def summary(session: SessionDep, project: ProjectDep) -> DashboardSummary:
    requests = RequestRepository(session)
    since = requests.start_of_today()

    kpis = await requests.summary(project.id, since=since)
    model_usage = await requests.usage_by_model(project.id, since=since)
    provider_usage = await requests.usage_by_provider(project.id, since=since)
    active_deployments = await DeploymentRepository(session).count_active(project.id)
    gpu_util = await GpuSampleRepository(session).avg_gpu_util(within_minutes=5)

    return DashboardSummary(
        requests_today=kpis["request_count"],
        cost_today_usd=kpis["cost_usd"],
        avg_latency_ms=kpis["avg_latency_ms"],
        success_rate_pct=kpis["success_rate_pct"],
        error_rate_pct=kpis["error_rate_pct"],
        tokens_used_today=kpis["tokens_used"],
        requests_per_minute=kpis["requests_per_minute"],
        model_usage=[ModelUsage(**m) for m in model_usage],
        provider_usage=[ProviderUsage(**p) for p in provider_usage],
        active_deployments=active_deployments,
        # None, not 0.0: a host with no GPU has no utilisation to report, and
        # a gauge pinned at zero reads as "idle GPU" rather than "no GPU".
        gpu_util_pct_avg=gpu_util,
    )


@router.get(
    "/timeseries",
    response_model=TimeseriesResponse,
    summary="Requests / cost / latency / errors over time",
)
async def timeseries(
    session: SessionDep,
    project: ProjectDep,
    hours: int = Query(24, ge=1, le=8760),
    granularity: str = Query("hour", pattern="^(minute|hour|day)$"),
) -> TimeseriesResponse:
    until = datetime.now(timezone.utc)
    since = until - _delta(hours)
    points = await RequestRepository(session).timeseries(
        project.id,
        since=since,
        until=until,
        granularity=granularity,  # type: ignore[arg-type]
    )
    return TimeseriesResponse(
        granularity=granularity,
        since=since,
        until=until,
        points=[TimeseriesPoint(**p) for p in points],
    )


@router.get(
    "/error-reasons",
    response_model=list[ErrorReason],
    summary="Top failure reasons (PRD 10)",
)
async def error_reasons(
    session: SessionDep,
    project: ProjectDep,
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(10, ge=1, le=50),
) -> list[ErrorReason]:
    since = datetime.now(timezone.utc) - _delta(hours)
    rows = await RequestRepository(session).error_reasons(
        project.id, since=since, limit=limit
    )
    return [ErrorReason(**r) for r in rows]


def _delta(hours: int):
    from datetime import timedelta

    return timedelta(hours=hours)
