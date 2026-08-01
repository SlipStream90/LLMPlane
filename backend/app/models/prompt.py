"""Prompt management with append-only versioning (PRD 6).

Versions are never mutated. "Rollback" creates a *new* version whose content
copies an older one, so the history stays a faithful audit trail. Diffs are
computed on read from two `PromptVersion.content` values — there is no
diff-storage table (data-models.md 2).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Prompt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prompt"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_prompt_project_name"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    versions: Mapped[list[PromptVersion]] = relationship(
        back_populates="prompt",
        cascade="all, delete-orphan",
        order_by="PromptVersion.version_number",
    )


class PromptVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prompt_version"
    __table_args__ = (
        UniqueConstraint(
            "prompt_id", "version_number", name="uq_prompt_version_number"
        ),
    )

    prompt_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("prompt.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Monotonic per prompt, assigned server-side.
    version_number: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    #: `{{var}}` names extracted at save time.
    variables: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    prompt: Mapped[Prompt] = relationship(back_populates="versions")
