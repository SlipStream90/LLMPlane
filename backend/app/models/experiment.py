"""Experiment tracking (PRD 7)."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Experiment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiment"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    runs: Mapped[list["ExperimentRun"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiment_run"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("experiment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: RESTRICT across aggregate boundaries: deleting a Prompt must not
    #: silently orphan the experiments that referenced its versions
    #: (data-models.md preamble).
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
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    seed: Mapped[int | None] = mapped_column(nullable=True)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("request.id", ondelete="SET NULL"), nullable=True
    )
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Reserved for Phase 2+ semantic search over experiment responses
    #: (PRD 7's "Embedding" field). Deliberately a plain nullable BYTEA, NOT a
    #: pgvector column: data-models.md 3 forbids enabling the pgvector
    #: extension in alpha for a feature that is not yet scheduled.
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    experiment: Mapped[Experiment] = relationship(back_populates="runs")
