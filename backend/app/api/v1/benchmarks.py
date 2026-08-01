"""Benchmark runs API (T028, backend half).

`POST /benchmarks/run` validates the grid, materialises one `BenchmarkRunItem`
per (row x prompt version x model x temperature) combination, and hands off to
the Celery chord in `workers/tasks/benchmark.py`. It returns 202 immediately —
a 400-item grid is minutes of work, not a request.

Items are created here rather than in the worker so that `total_items` is exact
from the moment the run is accepted, which is what makes the progress bar and
the `benchmark:{id}` WebSocket topic meaningful straight away.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app import workers_client
from app.api.deps import ProjectDep, SessionDep
from app.core.errors import NotFoundProblem, ValidationProblem
from app.models.benchmark import BenchmarkRun, BenchmarkRunItem
from app.models.enums import METRIC_NAME_ALLOWLIST, ItemStatus
from app.repositories.benchmark import (
    BenchmarkDatasetRepository,
    BenchmarkRunItemRepository,
    BenchmarkRunRepository,
)
from app.repositories.evaluation import EvaluationResultRepository
from app.repositories.prompt import PromptVersionRepository
from app.repositories.provider import ProviderModelRepository
from app.schemas.benchmark import (
    BenchmarkRunCreate,
    BenchmarkRunItemOut,
    BenchmarkRunOut,
)
from app.schemas.evaluation import EvaluationResultOut
from app.services.dataset_service import read_dataset

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])

#: A single run is capped so one request cannot queue an unbounded amount of
#: paid inference. Users split larger sweeps into multiple runs.
MAX_ITEMS_PER_RUN = 5000


@router.get("", response_model=list[BenchmarkRunOut], summary="List benchmark runs")
async def list_runs(session: SessionDep, project: ProjectDep) -> list[BenchmarkRunOut]:
    runs = await BenchmarkRunRepository(session).list_for_project(project.id)
    return [BenchmarkRunOut.model_validate(r) for r in runs]


@router.post(
    "/run",
    response_model=BenchmarkRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a benchmark run (Celery chord fan-out)",
)
async def start_run(
    payload: BenchmarkRunCreate, session: SessionDep, project: ProjectDep
) -> BenchmarkRunOut:
    datasets = BenchmarkDatasetRepository(session)
    dataset = await datasets.get(payload.dataset_id, project_id=project.id)
    if dataset is None:
        raise NotFoundProblem("Benchmark dataset", payload.dataset_id)

    bad_metrics = sorted(set(payload.metrics) - METRIC_NAME_ALLOWLIST)
    if bad_metrics:
        raise ValidationProblem(
            f"Unknown metric(s): {', '.join(bad_metrics)}. Supported metrics: "
            f"{', '.join(sorted(METRIC_NAME_ALLOWLIST))}",
            {"unknown_metrics": bad_metrics},
        )

    if "llm_judge_score" in payload.metrics and not payload.judge_model_id:
        raise ValidationProblem(
            "judge_model_id is required when 'llm_judge_score' is requested."
        )

    models = await ProviderModelRepository(session).get_many(
        project.id, payload.provider_model_ids
    )
    found = {m.id for m in models}
    missing = [str(m) for m in payload.provider_model_ids if m not in found]
    if missing:
        raise ValidationProblem(
            f"provider_model_ids not found in this project: {', '.join(missing)}"
        )

    version_repo = PromptVersionRepository(session)
    prompt_version_ids: list[uuid.UUID | None] = []
    for version_id in payload.prompt_version_ids:
        version = await version_repo.get(version_id)
        if version is None:
            raise NotFoundProblem("Prompt version", version_id)
        prompt_version_ids.append(version_id)
    if not prompt_version_ids:
        # No prompt template: dataset rows are used as the prompt directly.
        prompt_version_ids = [None]

    try:
        parsed = read_dataset(dataset.storage_path, dataset.source_format)
    except FileNotFoundError as exc:
        raise NotFoundProblem("Benchmark dataset file", dataset.storage_path) from exc

    total = (
        len(parsed.rows)
        * len(prompt_version_ids)
        * len(payload.provider_model_ids)
        * len(payload.temperatures)
    )
    if total > MAX_ITEMS_PER_RUN:
        raise ValidationProblem(
            f"This grid would create {total} items, above the {MAX_ITEMS_PER_RUN} "
            "per-run limit. Reduce the dataset, models or temperatures, or split "
            "it into several runs.",
            {"requested_items": total, "limit": MAX_ITEMS_PER_RUN},
        )

    runs = BenchmarkRunRepository(session)
    run = await runs.add(
        BenchmarkRun(
            project_id=project.id,
            dataset_id=dataset.id,
            prompt_version_ids=[str(v) for v in prompt_version_ids if v],
            provider_model_ids=[str(m) for m in payload.provider_model_ids],
            temperatures=payload.temperatures,
            metrics=payload.metrics,
            judge_model_id=payload.judge_model_id,
            total_items=total,
            completed_items=0,
        )
    )

    items = [
        BenchmarkRunItem(
            benchmark_run_id=run.id,
            dataset_row_index=row_index,
            prompt_version_id=version_id,
            provider_model_id=model_id,
            temperature=temperature,
            status=ItemStatus.PENDING,
        )
        for row_index in range(len(parsed.rows))
        for version_id in prompt_version_ids
        for model_id in payload.provider_model_ids
        for temperature in payload.temperatures
    ]
    await BenchmarkRunItemRepository(session).bulk_add(items)

    # Commit before enqueueing so the worker cannot outrun the write.
    await session.commit()
    run.celery_task_id = workers_client.launch_benchmark_run(run.id)
    await session.flush()

    return BenchmarkRunOut.model_validate(run)


@router.get(
    "/{run_id}", response_model=BenchmarkRunOut, summary="Benchmark run status/progress"
)
async def get_run(
    run_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> BenchmarkRunOut:
    run = await BenchmarkRunRepository(session).get(run_id, project_id=project.id)
    if run is None:
        raise NotFoundProblem("Benchmark run", run_id)
    return BenchmarkRunOut.model_validate(run)


@router.get(
    "/{run_id}/items",
    response_model=list[BenchmarkRunItemOut],
    summary="Per-combination results for a run",
)
async def get_run_items(
    run_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> list[BenchmarkRunItemOut]:
    run = await BenchmarkRunRepository(session).get(run_id, project_id=project.id)
    if run is None:
        raise NotFoundProblem("Benchmark run", run_id)
    items = await BenchmarkRunItemRepository(session).list_for_run(run_id)
    return [BenchmarkRunItemOut.model_validate(i) for i in items]


@router.get(
    "/{run_id}/results",
    response_model=list[EvaluationResultOut],
    summary="Evaluation results for a run",
)
async def get_run_results(
    run_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> list[EvaluationResultOut]:
    run = await BenchmarkRunRepository(session).get(run_id, project_id=project.id)
    if run is None:
        raise NotFoundProblem("Benchmark run", run_id)
    results = await EvaluationResultRepository(session).list_for_benchmark_run(
        project.id, run_id
    )
    return [EvaluationResultOut.model_validate(r) for r in results]
