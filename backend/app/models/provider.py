"""Provider connections and their model catalog (PRD 3.1 / 3.3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import HealthStatus, ProviderType


def _enum(python_enum: type, name: str) -> SAEnum:
    return SAEnum(
        python_enum,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
    )


class Provider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider"
    __table_args__ = (
        UniqueConstraint("project_id", "display_name", name="uq_provider_project_name"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_type: Mapped[ProviderType] = mapped_column(
        _enum(ProviderType, "provider_type"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)

    #: Set when this provider is backed by a plugin (any plugin-registered
    #: type, including CUSTOM and first-party plugins like "ollama"). Null
    #: for providers created before the plugin system existed, or for a
    #: first-party type with no plugin equivalent. References
    #: PluginRegistry manifest ids, not a DB foreign key — the registry is
    #: process-local and file-defined, not a table (R2).
    plugin_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    #: Fernet-encrypted JSON blob (API key + provider-specific fields such as
    #: an Azure endpoint/deployment name). Never returned by any API response
    #: and never logged (Article XII). See services/credential_service.py.
    credentials_encrypted: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )

    #: Set for local/self-hosted backends (Ollama/vLLM); null for hosted cloud
    #: providers, which use LiteLLM's built-in default endpoints.
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    #: Written by the periodic health-check task, never computed on read.
    health_status: Mapped[HealthStatus] = mapped_column(
        _enum(HealthStatus, "health_status"),
        nullable=False,
        default=HealthStatus.UNKNOWN,
        server_default=HealthStatus.UNKNOWN.value,
    )
    last_health_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_latency_ms: Mapped[int | None] = mapped_column(nullable=True)

    models: Mapped[list["ProviderModel"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan", lazy="selectin"
    )


class ProviderModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Model catalog entry. Static/config-seeded in alpha — pricing and
    rate-limit metadata are not live-synced from provider APIs (PRD 3.1)."""

    __tablename__ = "provider_model"
    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_provider_model_model_id"),
    )

    provider_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("provider.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    context_window: Mapped[int] = mapped_column(nullable=False, default=8192)
    input_price_per_1m: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    output_price_per_1m: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    capabilities: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    provider: Mapped[Provider] = relationship(back_populates="models")
