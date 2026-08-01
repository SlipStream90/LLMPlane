"""Gateway traffic log.

The highest-volume table in the system. Written exclusively by the Redis
Streams consumer (ADR-004) — the gateway never writes Postgres on the
inference hot path. Dashboard, cost analytics and the leaderboard all read
this table rather than maintaining per-feature duplicates.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import RequestStatus
from app.models.provider import _enum


class Request(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "request"
    __table_args__ = (
        # The primary dashboard/cost query pattern (api-contracts.md 3).
        Index("ix_request_project_requested_at", "project_id", "requested_at"),
        Index("ix_request_project_model", "project_id", "model_id"),
        Index("ix_request_trace_id", "trace_id"),
        # Idempotency key for at-least-once Redis Stream delivery: the same
        # gateway event replayed after a consumer restart must not create a
        # second row (ADR-004 consequences).
        Index("uq_request_event_id", "event_id", unique=True),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("api_key.id", ondelete="SET NULL"), nullable=True
    )
    routing_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("routing_policy.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("provider.id", ondelete="SET NULL"), nullable=True
    )
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        _enum(RequestStatus, "request_status"), nullable=False
    )
    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(14, 8), nullable=False, default=Decimal("0"), server_default="0"
    )
    latency_ms: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    ttft_ms: Mapped[int | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Correlates to the Langfuse trace for span-level drill-down. Span detail
    #: itself is NOT stored in Postgres (ADR-004 / api-contracts.md traces).
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Origin tagging: playground / benchmark:{id} / experiment:{id} / api.
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    #: Redis Stream message id, for at-least-once de-duplication.
    event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
