"""Evaluations query API (T029) — filterable read across `EvaluationResult`."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import PaginationDep, ProjectDep, SessionDep
from app.core.errors import ValidationProblem
from app.models.enums import METRIC_NAME_ALLOWLIST, MetricSource
from app.repositories.evaluation import EvaluationResultRepository
from app.schemas.common import Page
from app.schemas.evaluation import EvaluationResultOut, MetricTrendPoint

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("", response_model=Page[EvaluationResultOut], summary="Query evaluations")
async def query_evaluations(
    session: SessionDep,
    project: ProjectDep,
    pagination: PaginationDep,
    metric_name: str | None = Query(None),
    metric_source: MetricSource | None = Query(None),
    min_value: float | None = Query(None),
    max_value: float | None = Query(None),
    experiment_run_id: uuid.UUID | None = Query(None),
    benchmark_run_id: uuid.UUID | None = Query(None),
    since: datetime | None = Query(None),
) -> Page[EvaluationResultOut]:
    if metric_name and metric_name not in METRIC_NAME_ALLOWLIST:
        raise ValidationProblem(
            f"Unknown metric_name '{metric_name}'. Supported metrics: "
            f"{', '.join(sorted(METRIC_NAME_ALLOWLIST))}"
        )
    if min_value is not None and max_value is not None and min_value > max_value:
        raise ValidationProblem("min_value cannot exceed max_value.")

    repo = EvaluationResultRepository(session)
    page = await repo.list_page(
        stmt=repo.query_stmt(
            project.id,
            metric_name=metric_name,
            metric_source=metric_source.value if metric_source else None,
            min_value=min_value,
            max_value=max_value,
            experiment_run_id=experiment_run_id,
            benchmark_run_id=benchmark_run_id,
            since=since,
        ),
        cursor=pagination.cursor,
        limit=pagination.limit,
    )
    return Page[EvaluationResultOut](
        data=[EvaluationResultOut.model_validate(r) for r in page.data],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/metrics",
    response_model=list[str],
    summary="Metric names this deployment can record",
)
async def list_metrics() -> list[str]:
    """The app-level allowlist behind the open `metric_name` column
    (data-models.md 2), exposed so the UI's filters cannot drift from it."""
    return sorted(METRIC_NAME_ALLOWLIST)


@router.get(
    "/trend",
    response_model=list[MetricTrendPoint],
    summary="Average of one metric over time (PRD 10: evaluation trends)",
)
async def metric_trend(
    session: SessionDep,
    project: ProjectDep,
    metric_name: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    granularity: str = Query("day", pattern="^(hour|day|week)$"),
) -> list[MetricTrendPoint]:
    if metric_name not in METRIC_NAME_ALLOWLIST:
        raise ValidationProblem(f"Unknown metric_name '{metric_name}'.")

    from app.repositories.request import RequestRepository  # window helper

    points = await EvaluationResultRepository(session).metric_trend(
        project.id,
        metric_name,
        since=RequestRepository.window(days),
        granularity=granularity,
    )
    return [MetricTrendPoint(**p) for p in points]
