"""Experiment / ExperimentRun repositories."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, or_, select

from app.models.experiment import Experiment, ExperimentRun
from app.repositories.base import BaseRepository


class ExperimentRepository(BaseRepository[Experiment]):
    model = Experiment

    def search_stmt(
        self,
        project_id: uuid.UUID,
        *,
        query: str | None = None,
        tag: str | None = None,
    ) -> Select[Any]:
        stmt = select(Experiment).where(Experiment.project_id == project_id)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(Experiment.name.ilike(pattern), Experiment.notes.ilike(pattern))
            )
        if tag:
            # JSONB containment: `tags @> '["<tag>"]'`
            stmt = stmt.where(Experiment.tags.contains([tag]))
        return stmt


class ExperimentRunRepository(BaseRepository[ExperimentRun]):
    model = ExperimentRun

    def for_experiment_stmt(
        self,
        experiment_id: uuid.UUID,
        *,
        provider_model_id: uuid.UUID | None = None,
    ) -> Select[Any]:
        stmt = select(ExperimentRun).where(ExperimentRun.experiment_id == experiment_id)
        if provider_model_id:
            stmt = stmt.where(ExperimentRun.provider_model_id == provider_model_id)
        return stmt

    async def list_for_experiment(self, experiment_id: uuid.UUID) -> list[ExperimentRun]:
        stmt = self.for_experiment_stmt(experiment_id).order_by(
            ExperimentRun.created_at.desc()
        )
        return list((await self.session.execute(stmt)).scalars().all())
