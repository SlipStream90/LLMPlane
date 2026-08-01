"""Cost analytics (T032, PRD 12).

A separate route module from `dashboard.py` on purpose — both were scheduled in
the same parallel batch and sharing one file would have been a write conflict
(backlog T032 note).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Query

from app.api.deps import ProjectDep, SessionDep
from app.repositories.request import RequestRepository
from app.schemas.analytics import (
    CostBreakdownItem,
    CostBreakdownResponse,
    CostForecast,
    TimeseriesPoint,
    TimeseriesResponse,
)

router = APIRouter(prefix="/cost", tags=["cost-analytics"])

Dimension = Literal["model", "provider", "day", "tag"]


@router.get(
    "/breakdown",
    response_model=CostBreakdownResponse,
    summary="Cost grouped by model, provider, day or origin tag",
)
async def breakdown(
    session: SessionDep,
    project: ProjectDep,
    dimension: Dimension = Query("model"),
    days: int = Query(30, ge=1, le=365),
) -> CostBreakdownResponse:
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=days)
    rows = await RequestRepository(session).cost_breakdown(
        project.id, since=since, until=until, dimension=dimension
    )
    items = [CostBreakdownItem(**r) for r in rows]
    return CostBreakdownResponse(
        dimension=dimension,
        since=since,
        until=until,
        total_cost_usd=round(sum(i.cost_usd for i in items), 8),
        items=sorted(items, key=lambda i: -i.cost_usd),
    )


@router.get(
    "/over-time",
    response_model=TimeseriesResponse,
    summary="Cost over time",
)
async def over_time(
    session: SessionDep,
    project: ProjectDep,
    days: int = Query(30, ge=1, le=365),
    granularity: str = Query("day", pattern="^(hour|day)$"),
) -> TimeseriesResponse:
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=days)
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
    "/forecast",
    response_model=CostForecast,
    summary="Month-end cost projection",
)
async def forecast(
    session: SessionDep,
    project: ProjectDep,
    lookback_days: int = Query(14, ge=1, le=90),
) -> CostForecast:
    """Straight-line projection from the observed daily mean.

    Explicitly labelled as such in the response (`method`): with weeks of data
    at alpha, a fitted model would be false precision, and a consumer that can
    see how the number was produced can decide how much to trust it.
    """
    requests = RequestRepository(session)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=lookback_days)

    daily = await requests.cost_breakdown(
        project.id, since=since, until=now, dimension="day"
    )
    observed_days = max(len(daily), 1)
    avg_daily = sum(d["cost_usd"] for d in daily) / observed_days if daily else 0.0

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_to_date = (await requests.summary(project.id, since=month_start, until=now))[
        "cost_usd"
    ]
    days_remaining = _days_left_in_month(now)

    return CostForecast(
        method="linear projection from mean daily spend over the lookback window",
        days_observed=observed_days,
        avg_daily_cost_usd=round(avg_daily, 6),
        projected_month_end_usd=round(month_to_date + avg_daily * days_remaining, 4),
        month_to_date_usd=round(month_to_date, 4),
    )


def _days_left_in_month(now: datetime) -> int:
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1)
    else:
        next_month = now.replace(month=now.month + 1, day=1)
    return max((next_month.date() - now.date()).days, 0)
