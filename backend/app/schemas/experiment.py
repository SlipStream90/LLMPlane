"""Experiment tracking schemas (PRD 7)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=10_000)
    tags: list[str] = Field(default_factory=list)


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=10_000)
    tags: list[str] | None = None


class ExperimentOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    notes: str | None = None
    tags: list[str]
    created_at: datetime


class ExperimentRunCreate(BaseModel):
    prompt_version_id: uuid.UUID | None = None
    provider_model_id: uuid.UUID
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    seed: int | None = None
    request_id: uuid.UUID | None = None
    response_text: str | None = None


class ExperimentRunOut(ORMModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    prompt_version_id: uuid.UUID | None = None
    provider_model_id: uuid.UUID
    temperature: float
    seed: int | None = None
    request_id: uuid.UUID | None = None
    response_text: str | None = None
    created_at: datetime
