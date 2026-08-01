"""Side-by-side playground schemas (PRD 5)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class PlaygroundCompareRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    system_prompt: str | None = Field(default=None, max_length=100_000)
    model_ids: list[str] = Field(min_length=2)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32_000)

    @field_validator("model_ids")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("model_ids must be unique")
        return v


class PlaygroundResponseItem(BaseModel):
    provider_model_id: uuid.UUID | None = None
    model_id: str
    response_text: str | None = None
    #: Set instead of `response_text` when this one model failed. A failed
    #: model never fails the whole comparison (Article XIV).
    error: str | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    judge_score: float | None = None


class PlaygroundCompareResponse(BaseModel):
    comparison_id: uuid.UUID
    responses: list[PlaygroundResponseItem]


class PlaygroundVoteRequest(BaseModel):
    response_id: uuid.UUID
    vote: bool


class PlaygroundComparisonOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    prompt_text: str
    system_prompt: str | None = None
    temperature: float
    created_at: datetime
