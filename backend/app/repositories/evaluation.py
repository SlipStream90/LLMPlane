"""EvaluationResult repository — the query surface behind /evaluations,
/benchmarks/{id}/results and the quality half of the leaderboard."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select as SASelect
from sqlalchemy import func, select

from app.models.benchmark import BenchmarkRunItem
from app.models.evaluation import EvaluationResult
from app.models.provider import ProviderModel
from app.repositories.base import BaseRepository

__all__ = ["EvaluationResultRepository"]


class EvaluationResultRepository(BaseRepository[EvaluationResult]):
    model = EvaluationResult

    def query_stmt(
        self,
        project_id: uuid.UUID,
        *,
        metric_name: str | None = None,
        metric_source: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        experiment_run_id: uuid.UUID | None = None,
        benchmark_run_id: uuid.UUID | None = None,
        since: datetime | None = None,
    ) -> SASelect[Any]:
        stmt = select(EvaluationResult).where(EvaluationResult.project_id == project_id)
        if metric_name:
            stmt = stmt.where(EvaluationResult.metric_name == metric_name)
        if metric_source:
            stmt = stmt.where(EvaluationResult.metric_source == metric_source)
        if min_value is not None:
            stmt = stmt.where(EvaluationResult.value >= min_value)
        if max_value is not None:
            stmt = stmt.where(EvaluationResult.value <= max_value)
        if experiment_run_id:
            stmt = stmt.where(EvaluationResult.experiment_run_id == experiment_run_id)
        if benchmark_run_id:
            # Join through run items — callers filter by *run*, the table
            # stores the *item*.
            stmt = stmt.where(
                EvaluationResult.benchmark_run_item_id.in_(
                    select(BenchmarkRunItem.id).where(
                        BenchmarkRunItem.benchmark_run_id == benchmark_run_id
                    )
                )
            )
        if since:
            stmt = stmt.where(EvaluationResult.created_at >= since)
        return stmt

    async def list_for_benchmark_run(
        self, project_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[EvaluationResult]:
        stmt = self.query_stmt(project_id, benchmark_run_id=run_id).order_by(
            EvaluationResult.metric_name
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def metric_averages_by_model(
        self, project_id: uuid.UUID, *, since: datetime | None = None
    ) -> dict[str, dict[str, float]]:
        """``{model_id: {metric_name: avg_value}}`` for benchmark-derived
        scores, which is what the leaderboard's quality columns are built on.

        Experiment-derived scores are excluded on purpose: benchmarks run a
        controlled prompt/model/temperature grid, so their averages are
        comparable across models. Ad-hoc experiment runs are not, and mixing
        them would make the leaderboard's ranking meaningless.
        """
        stmt = (
            select(
                ProviderModel.model_id,
                EvaluationResult.metric_name,
                func.avg(EvaluationResult.value).label("avg_value"),
            )
            .join(
                BenchmarkRunItem,
                BenchmarkRunItem.id == EvaluationResult.benchmark_run_item_id,
            )
            .join(
                ProviderModel,
                ProviderModel.id == BenchmarkRunItem.provider_model_id,
            )
            .where(EvaluationResult.project_id == project_id)
            .group_by(ProviderModel.model_id, EvaluationResult.metric_name)
        )
        if since:
            stmt = stmt.where(EvaluationResult.created_at >= since)

        out: dict[str, dict[str, float]] = {}
        for row in (await self.session.execute(stmt)).all():
            out.setdefault(row.model_id, {})[row.metric_name] = float(row.avg_value)
        return out

    async def metric_trend(
        self,
        project_id: uuid.UUID,
        metric_name: str,
        *,
        since: datetime,
        granularity: str = "day",
    ) -> list[dict[str, Any]]:
        bucket = func.date_trunc(granularity, EvaluationResult.created_at).label(
            "bucket"
        )
        stmt = (
            select(bucket, func.avg(EvaluationResult.value).label("avg_value"))
            .where(
                EvaluationResult.project_id == project_id,
                EvaluationResult.metric_name == metric_name,
                EvaluationResult.created_at >= since,
            )
            .group_by(bucket)
            .order_by(bucket)
        )
        return [
            {"bucket": r.bucket.isoformat(), "avg_value": float(r.avg_value)}
            for r in (await self.session.execute(stmt)).all()
        ]
