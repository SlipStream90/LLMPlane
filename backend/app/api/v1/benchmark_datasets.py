"""Benchmark datasets API (T024): multipart upload, list, preview, delete."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import ProjectDep, SessionDep
from app.core.config import get_settings
from app.core.errors import ConflictProblem, NotFoundProblem, ValidationProblem
from app.models.benchmark import BenchmarkDataset
from app.repositories.benchmark import BenchmarkDatasetRepository
from app.schemas.benchmark import BenchmarkDatasetOut, DatasetPreview
from app.services.dataset_service import (
    delete_dataset_file,
    detect_format,
    parse_dataset,
    read_dataset,
    storage_path_for,
    write_dataset,
)

router = APIRouter(prefix="/benchmark-datasets", tags=["benchmark-datasets"])


@router.get("", response_model=list[BenchmarkDatasetOut], summary="List datasets")
async def list_datasets(
    session: SessionDep, project: ProjectDep
) -> list[BenchmarkDatasetOut]:
    rows = await BenchmarkDatasetRepository(session).list_for_project(project.id)
    return [BenchmarkDatasetOut.model_validate(d) for d in rows]


@router.post(
    "",
    response_model=BenchmarkDatasetOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a benchmark dataset (CSV/JSON, multipart)",
)
async def upload_dataset(
    session: SessionDep,
    project: ProjectDep,
    file: UploadFile = File(...),
    name: str = Form(...),
) -> BenchmarkDatasetOut:
    """Validate first, then store.

    The file is fully parsed before anything is written to disk, so a malformed
    upload never leaves an unreadable file behind for a benchmark run to trip
    over later.
    """
    settings = get_settings()
    repo = BenchmarkDatasetRepository(session)

    if await repo.get_by_name(project.id, name):
        raise ConflictProblem(f"A dataset named '{name}' already exists.")

    raw = await file.read()
    if not raw:
        raise ValidationProblem("Uploaded file is empty.")
    if len(raw) > settings.max_upload_bytes:
        raise ValidationProblem(
            f"Dataset exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB "
            "upload limit."
        )

    source_format = detect_format(file.filename or "", file.content_type)
    parsed = parse_dataset(raw, source_format)

    dataset_id = uuid.uuid4()
    path = storage_path_for(dataset_id, source_format)
    write_dataset(path, raw)

    try:
        dataset = await repo.add(
            BenchmarkDataset(
                id=dataset_id,
                project_id=project.id,
                name=name,
                source_format=source_format,
                row_count=parsed.row_count,
                storage_path=path,
                columns=parsed.columns,
            )
        )
    except Exception:
        # Don't leave an orphan file behind if the row insert fails.
        delete_dataset_file(path)
        raise

    return BenchmarkDatasetOut.model_validate(dataset)


@router.get("/{dataset_id}", response_model=BenchmarkDatasetOut, summary="Get dataset")
async def get_dataset(
    dataset_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> BenchmarkDatasetOut:
    dataset = await BenchmarkDatasetRepository(session).get(
        dataset_id, project_id=project.id
    )
    if dataset is None:
        raise NotFoundProblem("Benchmark dataset", dataset_id)
    return BenchmarkDatasetOut.model_validate(dataset)


@router.get(
    "/{dataset_id}/preview",
    response_model=DatasetPreview,
    summary="Preview the first N rows",
)
async def preview_dataset(
    dataset_id: uuid.UUID,
    session: SessionDep,
    project: ProjectDep,
    limit: int = Query(10, ge=1, le=100),
) -> DatasetPreview:
    """Powers the run-launcher's column mapping UI."""
    dataset = await BenchmarkDatasetRepository(session).get(
        dataset_id, project_id=project.id
    )
    if dataset is None:
        raise NotFoundProblem("Benchmark dataset", dataset_id)
    try:
        parsed = read_dataset(dataset.storage_path, dataset.source_format)
    except FileNotFoundError as exc:
        raise NotFoundProblem("Benchmark dataset file", dataset.storage_path) from exc
    return DatasetPreview(
        columns=parsed.columns,
        rows=parsed.rows[:limit],
        row_count=parsed.row_count,
    )


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete dataset",
)
async def delete_dataset(
    dataset_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> None:
    repo = BenchmarkDatasetRepository(session)
    dataset = await repo.get(dataset_id, project_id=project.id)
    if dataset is None:
        raise NotFoundProblem("Benchmark dataset", dataset_id)
    path = dataset.storage_path
    await repo.delete(dataset)
    delete_dataset_file(path)
