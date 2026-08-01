"""Organization / Project / APIKey.

ADR-002: single-tenant alpha on a schema that already carries the FK shape
multi-tenancy needs. `Organization` holds exactly one seeded row; every
aggregate hangs off `Project`, which carries a required `organization_id`.
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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization"

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    projects: Mapped[list["Project"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="projects")
    api_keys: Mapped[list["APIKey"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class APIKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Project-scoped API key (PRD 15).

    Only the argon2id hash is stored. `key_prefix` is a non-secret display and
    lookup aid; authentication always verifies the full key against the hash.
    """

    __tablename__ = "api_key"
    __table_args__ = (
        Index("ix_api_key_project_prefix", "project_id", "key_prefix"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    rate_limit_rpm: Mapped[int | None] = mapped_column(nullable=True)
    quota_monthly_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="api_keys")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
