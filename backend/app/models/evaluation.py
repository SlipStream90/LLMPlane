"""Evaluation results — one table for every metric score (data-models.md 2).

Referenced polymorphically from exactly one of `ExperimentRun` or
`BenchmarkRunItem`; the XOR is enforced by a CHECK constraint in the database,
not only by application code.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MetricSource
from app.models.provider import _enum


class EvaluationResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_result"
    __table_args__ = (
        CheckConstraint(
            "(experiment_run_id IS NULL) <> (benchmark_run_item_id IS NULL)",
            name="exactly_one_parent",
        ),
        Index("ix_evaluation_result_metric", "metric_name", "value"),
        Index("ix_evaluation_result_project_metric", "project_id", "metric_name"),
    )

    #: Denormalised from the parent run for query scoping. Every list endpoint
    #: filters by project, and joining three levels up on the hottest read path
    #: (leaderboard, evaluations query) is not worth the normalisation purity.
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    experiment_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("experiment_run.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    benchmark_run_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("benchmark_run_item.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    #: Open string with an app-level allowlist (models/enums.py), not a DB
    #: enum — the RAGAS/DeepEval/Promptfoo metric sets evolve faster than a
    #: migration cycle.
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_source: Mapped[MetricSource] = mapped_column(
        _enum(MetricSource, "metric_source"), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    #: Judge rationale text, per-criterion breakdown, scorer version, etc.
    #: Named `meta` in Python because `metadata` is reserved on Declarative
    #: classes; the column itself is `metadata` as the data model specifies.
    meta: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
