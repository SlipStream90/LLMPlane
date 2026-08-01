"""Side-by-side playground comparisons (PRD 5)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlaygroundComparison(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "playground_comparison"

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)

    responses: Mapped[list["PlaygroundResponse"]] = relationship(
        back_populates="comparison", cascade="all, delete-orphan", lazy="selectin"
    )


class PlaygroundResponse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "playground_response"

    comparison_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("playground_comparison.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_model_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("provider_model.id", ondelete="RESTRICT"),
        nullable=True,
    )
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("request.id", ondelete="SET NULL"), nullable=True
    )
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Set when this model's call failed while others succeeded — a partial
    #: failure is recorded, never allowed to fail the whole comparison
    #: (Article XIV, api-contracts.md 3).
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 8), nullable=True)
    user_vote: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    judge_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    comparison: Mapped[PlaygroundComparison] = relationship(back_populates="responses")
