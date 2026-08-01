"""Prompt, version, and diff schemas (PRD 6)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    #: Optional initial version, so creating a usable prompt is one call.
    content: str | None = Field(default=None, max_length=100_000)
    system_prompt: str | None = Field(default=None, max_length=100_000)


class PromptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class PromptOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    latest_version_number: int = 0


class PromptVersionCreate(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)
    system_prompt: str | None = Field(default=None, max_length=100_000)
    note: str | None = Field(default=None, max_length=1000)


class PromptVersionOut(ORMModel):
    id: uuid.UUID
    prompt_id: uuid.UUID
    version_number: int
    content: str
    variables: list[str]
    system_prompt: str | None = None
    created_by_note: str | None = None
    created_at: datetime


class DiffOp(BaseModel):
    op: Literal["equal", "insert", "delete", "replace"]
    text: str


class PromptDiffOut(BaseModel):
    from_version: int
    to_version: int
    diff: list[DiffOp]


class PromptRollbackRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
