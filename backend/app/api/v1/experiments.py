"""Experiments API (T023): CRUD plus searchable/filterable run listing."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import PaginationDep, ProjectDep, SessionDep
from app.core.errors import NotFoundProblem
from app.models.experiment import Experiment, ExperimentRun
from app.repositories.experiment import ExperimentRepository, ExperimentRunRepository
from app.schemas.common import Page
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentOut,
    ExperimentRunCreate,
    ExperimentRunOut,
    ExperimentUpdate,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=Page[ExperimentOut], summary="List/search experiments")
async def list_experiments(
    session: SessionDep,
    project: ProjectDep,
    pagination: PaginationDep,
    q: str | None = Query(None, description="Substring match on name or notes"),
    tag: str | None = Query(None, description="Exact tag match"),
) -> Page[ExperimentOut]:
    repo = ExperimentRepository(session)
    page = await repo.list_page(
        stmt=repo.search_stmt(project.id, query=q, tag=tag),
        cursor=pagination.cursor,
        limit=pagination.limit,
    )
    return Page[ExperimentOut](
        data=[ExperimentOut.model_validate(e) for e in page.data],
        next_cursor=page.next_cursor,
    )


@router.post(
    "",
    response_model=ExperimentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create experiment",
)
async def create_experiment(
    payload: ExperimentCreate, session: SessionDep, project: ProjectDep
) -> ExperimentOut:
    experiment = await ExperimentRepository(session).add(
        Experiment(
            project_id=project.id,
            name=payload.name,
            notes=payload.notes,
            tags=payload.tags,
        )
    )
    return ExperimentOut.model_validate(experiment)


@router.get("/{experiment_id}", response_model=ExperimentOut, summary="Get experiment")
async def get_experiment(
    experiment_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> ExperimentOut:
    experiment = await ExperimentRepository(session).get(
        experiment_id, project_id=project.id
    )
    if experiment is None:
        raise NotFoundProblem("Experiment", experiment_id)
    return ExperimentOut.model_validate(experiment)


@router.patch(
    "/{experiment_id}", response_model=ExperimentOut, summary="Update experiment"
)
async def update_experiment(
    experiment_id: uuid.UUID,
    payload: ExperimentUpdate,
    session: SessionDep,
    project: ProjectDep,
) -> ExperimentOut:
    experiment = await ExperimentRepository(session).get(
        experiment_id, project_id=project.id
    )
    if experiment is None:
        raise NotFoundProblem("Experiment", experiment_id)
    if payload.name is not None:
        experiment.name = payload.name
    if payload.notes is not None:
        experiment.notes = payload.notes
    if payload.tags is not None:
        experiment.tags = payload.tags
    await session.flush()
    return ExperimentOut.model_validate(experiment)


@router.delete(
    "/{experiment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete experiment",
)
async def delete_experiment(
    experiment_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> None:
    repo = ExperimentRepository(session)
    experiment = await repo.get(experiment_id, project_id=project.id)
    if experiment is None:
        raise NotFoundProblem("Experiment", experiment_id)
    await repo.delete(experiment)


@router.get(
    "/{experiment_id}/runs",
    response_model=Page[ExperimentRunOut],
    summary="List experiment runs",
)
async def list_runs(
    experiment_id: uuid.UUID,
    session: SessionDep,
    project: ProjectDep,
    pagination: PaginationDep,
    provider_model_id: uuid.UUID | None = None,
) -> Page[ExperimentRunOut]:
    await _require_experiment(session, experiment_id, project.id)
    repo = ExperimentRunRepository(session)
    page = await repo.list_page(
        stmt=repo.for_experiment_stmt(
            experiment_id, provider_model_id=provider_model_id
        ),
        cursor=pagination.cursor,
        limit=pagination.limit,
    )
    return Page[ExperimentRunOut](
        data=[ExperimentRunOut.model_validate(r) for r in page.data],
        next_cursor=page.next_cursor,
    )


@router.post(
    "/{experiment_id}/runs",
    response_model=ExperimentRunOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record an experiment run",
)
async def create_run(
    experiment_id: uuid.UUID,
    payload: ExperimentRunCreate,
    session: SessionDep,
    project: ProjectDep,
) -> ExperimentRunOut:
    await _require_experiment(session, experiment_id, project.id)
    run = await ExperimentRunRepository(session).add(
        ExperimentRun(
            experiment_id=experiment_id,
            prompt_version_id=payload.prompt_version_id,
            provider_model_id=payload.provider_model_id,
            temperature=payload.temperature,
            seed=payload.seed,
            request_id=payload.request_id,
            response_text=payload.response_text,
        )
    )
    return ExperimentRunOut.model_validate(run)


async def _require_experiment(
    session, experiment_id: uuid.UUID, project_id: uuid.UUID
) -> None:
    if (
        await ExperimentRepository(session).get(experiment_id, project_id=project_id)
        is None
    ):
        raise NotFoundProblem("Experiment", experiment_id)
