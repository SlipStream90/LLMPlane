"""Dashboard, cost analytics and trace schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import RequestStatus
from app.schemas.common import ORMModel


class ModelUsage(BaseModel):
    model_id: str
    request_count: int
    cost_usd: float
    tokens: int = 0


class ProviderUsage(BaseModel):
    provider_type: str
    request_count: int
    cost_usd: float


class DashboardSummary(BaseModel):
    """KPI roll-up for today (api-contracts.md 3).

    Eventually consistent with gateway traffic by design: request rows arrive
    through the Redis Stream consumer, typically sub-second behind the call
    itself (ADR-004). Do not build anything on top of this that assumes
    transactional consistency with the gateway.
    """

    requests_today: int
    cost_today_usd: float
    avg_latency_ms: float
    success_rate_pct: float
    error_rate_pct: float
    tokens_used_today: int
    requests_per_minute: float
    model_usage: list[ModelUsage]
    provider_usage: list[ProviderUsage]
    active_deployments: int
    gpu_util_pct_avg: float | None = None


class TimeseriesPoint(BaseModel):
    bucket: str
    request_count: int
    cost_usd: float
    avg_latency_ms: float
    tokens: int
    error_count: int


class TimeseriesResponse(BaseModel):
    granularity: str
    since: datetime
    until: datetime
    points: list[TimeseriesPoint]


class ErrorReason(BaseModel):
    reason: str
    count: int


class CostBreakdownItem(BaseModel):
    key: str
    cost_usd: float
    request_count: int


class CostBreakdownResponse(BaseModel):
    dimension: str
    since: datetime
    until: datetime
    total_cost_usd: float
    items: list[CostBreakdownItem]


class CostForecast(BaseModel):
    """Naive linear projection from the observed daily mean.

    Explicitly not a model: `method` is returned so a consumer can see how the
    number was produced rather than mistaking it for a fitted forecast.
    """

    method: str
    days_observed: int
    avg_daily_cost_usd: float
    projected_month_end_usd: float
    month_to_date_usd: float


class TraceOut(ORMModel):
    id: uuid.UUID
    trace_id: str | None = None
    project_id: uuid.UUID
    model_id: str
    status: RequestStatus
    latency_ms: int
    ttft_ms: int | None = None
    cost_usd: float
    input_tokens: int
    output_tokens: int
    error_message: str | None = None
    tags: list[str] = []
    requested_at: datetime


class TraceDetail(BaseModel):
    """Request row joined with Langfuse span detail when it is reachable.

    `langfuse_available=False` with a populated `detail_error` is a normal,
    honest response when Langfuse is not configured or is down — the request
    row we do own is still returned (Article XIV).
    """

    request: TraceOut | None = None
    langfuse_available: bool
    trace: dict[str, Any] | None = None
    detail_error: str | None = None
