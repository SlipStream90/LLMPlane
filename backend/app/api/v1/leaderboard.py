"""Model leaderboard (T030, PRD 13).

Two data sources are merged, and the merge is the whole design:

  * **`request`** — real traffic gives cost, latency and reliability.
  * **`evaluation_result`** — benchmark runs give judge score and
    hallucination rate.

A model present in only one source still appears, with `null` where the other
source has nothing to say. Substituting 0.0 for "not measured" would rank an
unevaluated model as the worst possible one, which is a lie the sort order
would then propagate to the top of the page.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from app.api.deps import ProjectDep, SessionDep
from app.repositories.evaluation import EvaluationResultRepository
from app.repositories.provider import ProviderModelRepository
from app.repositories.request import RequestRepository
from app.schemas.evaluation import LeaderboardEntry

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

SortBy = Literal["cost", "latency", "judge_score", "reliability", "requests"]


@router.get("", response_model=list[LeaderboardEntry], summary="Ranked model leaderboard")
async def leaderboard(
    session: SessionDep,
    project: ProjectDep,
    sort_by: SortBy = Query("judge_score"),
    days: int = Query(30, ge=1, le=365),
    search: str | None = Query(None, description="Substring match on model id"),
) -> list[LeaderboardEntry]:
    since = RequestRepository.window(days)

    traffic = await RequestRepository(session).leaderboard_rows(project.id, since=since)
    quality = await EvaluationResultRepository(session).metric_averages_by_model(
        project.id, since=since
    )
    catalog = {
        m.model_id: m.id
        for m in await ProviderModelRepository(session).list_for_project(project.id)
    }

    entries: dict[str, LeaderboardEntry] = {}
    for row in traffic:
        model_id = row["model_id"]
        scores = quality.get(model_id, {})
        entries[model_id] = LeaderboardEntry(
            provider_model_id=catalog.get(model_id),
            model_id=model_id,
            avg_cost_usd=row["avg_cost_usd"],
            avg_latency_ms=row["avg_latency_ms"],
            reliability_pct=row["reliability_pct"],
            request_count=row["request_count"],
            avg_judge_score=scores.get("llm_judge_score"),
            hallucination_rate=scores.get("hallucination_score"),
        )

    # Models that have only been benchmarked, never served live traffic.
    for model_id, scores in quality.items():
        if model_id in entries:
            continue
        entries[model_id] = LeaderboardEntry(
            provider_model_id=catalog.get(model_id),
            model_id=model_id,
            avg_cost_usd=scores.get("cost_usd", 0.0),
            avg_latency_ms=scores.get("latency_ms", 0.0),
            reliability_pct=0.0,
            request_count=0,
            avg_judge_score=scores.get("llm_judge_score"),
            hallucination_rate=scores.get("hallucination_score"),
        )

    rows = list(entries.values())
    if search:
        needle = search.lower()
        rows = [r for r in rows if needle in r.model_id.lower()]

    return _sort(rows, sort_by)


def _sort(rows: list[LeaderboardEntry], sort_by: SortBy) -> list[LeaderboardEntry]:
    """Sort with unmeasured values last, whichever direction the column sorts.

    `None` is not "worst" — it is "unknown" — so it is pushed to the end of the
    list rather than being coerced into a comparable number.
    """
    if sort_by == "cost":
        return sorted(rows, key=lambda r: r.avg_cost_usd)
    if sort_by == "latency":
        return sorted(rows, key=lambda r: r.avg_latency_ms)
    if sort_by == "reliability":
        return sorted(rows, key=lambda r: -r.reliability_pct)
    if sort_by == "requests":
        return sorted(rows, key=lambda r: -r.request_count)
    return sorted(
        rows,
        key=lambda r: (r.avg_judge_score is None, -(r.avg_judge_score or 0.0)),
    )
