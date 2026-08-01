"""Benchmark datasets, runs and per-combination run items (PRD 4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DatasetFormat, ItemStatus, RunStatus
from app.models.provider import _enum


class BenchmarkDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_dataset"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_format: Mapped[DatasetFormat] = mapped_column(
        _enum(DatasetFormat, "dataset_format"), nullable=False
    )
    row_count: Mapped[int] = mapped_column(nullable=False, default=0)
    #: Local Docker volume path — no object storage in alpha
    #: (infrastructure.md 4). Server-generated; never taken from user input.
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    #: Column names discovered at upload time, so the run launcher UI can map
    #: dataset columns onto prompt variables without re-reading the file.
    columns: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    runs: Mapped[list["BenchmarkRun"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class BenchmarkRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "benchmark_run"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("benchmark_dataset.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_version_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    provider_model_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    temperatures: Mapped[list[float]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    #: Metric names to score after generation, validated against
    #: `METRIC_NAME_ALLOWLIST` at request time. Not in data-models.md's original
    #: column list — added because the aggregation callback has to know which
    #: scorers to run, and re-deriving that from the API request would mean the
    #: worker could not resume a run it did not receive.
    metrics: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    #: Judge model for `llm_judge_score`, when that metric is requested.
    judge_model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        _enum(RunStatus, "run_status"),
        nullable=False,
        default=RunStatus.PENDING,
        server_default=RunStatus.PENDING.value,
        index=True,
    )
    total_items: Mapped[int] = mapped_column(nullable=False, default=0)
    completed_items: Mapped[int] = mapped_column(nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Celery chord id, so a stuck run can be traced back to its task graph.
    celery_task_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    dataset: Mapped[BenchmarkDataset] = relationship(back_populates="runs")
    items: Mapped[list["BenchmarkRunItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class BenchmarkRunItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One (dataset row x prompt version x model x temperature) combination."""

    __tablename__ = "benchmark_run_item"
    __table_args__ = (
        Index("ix_benchmark_run_item_run_status", "benchmark_run_id", "status"),
    )

    benchmark_run_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("benchmark_run.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_row_index: Mapped[int] = mapped_column(nullable=False)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("prompt_version.id", ondelete="RESTRICT"),
        nullable=True,
    )
    provider_model_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("provider_model.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("request.id", ondelete="SET NULL"), nullable=True
    )
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ItemStatus] = mapped_column(
        _enum(ItemStatus, "item_status"),
        nullable=False,
        default=ItemStatus.PENDING,
        server_default=ItemStatus.PENDING.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[BenchmarkRun] = relationship(back_populates="items")
