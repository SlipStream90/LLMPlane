"""Routing policies (PRD 3.4).

`backend` is the source of truth for policy; the gateway is a config-driven
executor (ARCHITECTURE.md 3.3).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RoutingStrategy
from app.models.provider import _enum


class RoutingPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "routing_policy"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_routing_policy_project_name"),
        # Exactly one active policy per project (data-models.md 2) — enforced
        # in the database by a partial unique index, not only in app code, so a
        # concurrent activate cannot produce two active policies.
        Index(
            "uq_routing_policy_one_active_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    strategy: Mapped[RoutingStrategy] = mapped_column(
        _enum(RoutingStrategy, "routing_strategy"), nullable=False
    )
    #: Strategy-specific params: fallback chain order, weight map, thresholds.
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    #: `ProviderModel.model_id` values eligible under this policy.
    model_allowlist: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
