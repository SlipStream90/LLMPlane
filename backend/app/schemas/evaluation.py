"""Evaluation result and leaderboard schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import MetricSource
from app.schemas.common import ORMModel


class EvaluationResultOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    experiment_run_id: uuid.UUID | None = None
    benchmark_run_item_id: uuid.UUID | None = None
    metric_name: str
    metric_source: MetricSource
    value: float
    meta: dict[str, Any] | None = None
    created_at: datetime


class MetricTrendPoint(BaseModel):
    bucket: str
    avg_value: float


class LeaderboardEntry(BaseModel):
    """One model's standing.

    Cost/latency/reliability come from real gateway traffic (`request`);
    judge score and hallucination rate come from benchmark evaluations. Either
    half can be absent — a model with traffic but no benchmark scores still
    appears, with nulls where quality data does not exist yet, rather than
    being silently dropped or shown as zero.
    """

    provider_model_id: uuid.UUID | None = None
    model_id: str
    avg_cost_usd: float
    avg_latency_ms: float
    avg_judge_score: float | None = None
    hallucination_rate: float | None = None
    reliability_pct: float
    request_count: int
