"""Local model deployments and host telemetry (PRD 3.2, ADR-003)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import DeploymentBackend, DeploymentStatus
from app.models.provider import _enum


class Deployment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deployment"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: The ollama/vllm-typed Provider row this deployment is registered under,
    #: so gateway routing sees local and cloud models uniformly.
    provider_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("provider.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    backend_type: Mapped[DeploymentBackend] = mapped_column(
        _enum(DeploymentBackend, "deployment_backend"), nullable=False
    )
    #: HF tag or Ollama model name. Passed as an *argument* to an allow-listed
    #: image, never as an arbitrary container spec (ARCHITECTURE.md 4.5).
    model_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    container_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[DeploymentStatus] = mapped_column(
        _enum(DeploymentStatus, "deployment_status"),
        nullable=False,
        default=DeploymentStatus.PENDING,
        server_default=DeploymentStatus.PENDING.value,
        index=True,
    )
    gpu_index: Mapped[int | None] = mapped_column(nullable=True)
    port: Mapped[int | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    download_progress_pct: Mapped[int | None] = mapped_column(nullable=True)

    samples: Mapped[list["GpuSample"]] = relationship(
        back_populates="deployment", cascade="all, delete-orphan"
    )


class GpuSample(UUIDPrimaryKeyMixin, Base):
    """Host telemetry sample (ADR-003).

    Deliberately data-source-agnostic: `nvidia-smi`/pynvml writes it today, a
    DCGM exporter can write it in Phase 2+ without the readers changing.
    High write volume with a short (72h default) retention window — see
    workers/tasks/retention.py.
    """

    __tablename__ = "gpu_sample"
    __table_args__ = (
        Index("ix_gpu_sample_sampled_at_desc", "sampled_at"),
        Index("ix_gpu_sample_deployment_sampled", "deployment_id", "sampled_at"),
    )

    deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("deployment.id", ondelete="CASCADE"),
        nullable=True,
    )
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    gpu_index: Mapped[int] = mapped_column(nullable=False)
    gpu_util_pct: Mapped[float] = mapped_column(Float, nullable=False)
    vram_used_mb: Mapped[int] = mapped_column(nullable=False)
    vram_total_mb: Mapped[int] = mapped_column(nullable=False)
    cpu_util_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    ram_used_mb: Mapped[int | None] = mapped_column(nullable=True)

    deployment: Mapped[Deployment | None] = relationship(back_populates="samples")
