"""Benchmark dataset / run schemas (PRD 4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DatasetFormat, ItemStatus, RunStatus
from app.schemas.common import ORMModel


class BenchmarkDatasetOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source_format: DatasetFormat
    row_count: int
    columns: list[str]
    created_at: datetime


class DatasetPreview(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class BenchmarkRunCreate(BaseModel):
    dataset_id: uuid.UUID
    prompt_version_ids: list[uuid.UUID] = Field(default_factory=list)
    provider_model_ids: list[uuid.UUID] = Field(min_length=1)
    temperatures: list[float] = Field(default_factory=lambda: [0.0])
    #: Metrics to score after generation. Validated against
    #: `METRIC_NAME_ALLOWLIST` in the route, where the DB session is available.
    metrics: list[str] = Field(default_factory=list)
    #: Required when `llm_judge_score` is among `metrics`.
    judge_model_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _validate_grid(self) -> "BenchmarkRunCreate":
        if not self.temperatures:
            self.temperatures = [0.0]
        for t in self.temperatures:
            if not 0.0 <= t <= 2.0:
                raise ValueError("temperatures must each be between 0.0 and 2.0")
        if len(self.provider_model_ids) != len(set(self.provider_model_ids)):
            raise ValueError("provider_model_ids must be unique")
        return self


class BenchmarkRunOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    dataset_id: uuid.UUID
    status: RunStatus
    total_items: int
    completed_items: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class BenchmarkRunItemOut(ORMModel):
    id: uuid.UUID
    benchmark_run_id: uuid.UUID
    dataset_row_index: int
    prompt_version_id: uuid.UUID | None = None
    provider_model_id: uuid.UUID
    temperature: float
    request_id: uuid.UUID | None = None
    response_text: str | None = None
    status: ItemStatus
    error_message: str | None = None
