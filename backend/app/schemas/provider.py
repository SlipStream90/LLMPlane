"""Provider and model-catalog schemas.

`ProviderOut` deliberately has no credential field of any kind: the encrypted
blob never leaves the server and the plaintext key is write-only
(ARCHITECTURE.md 4.1, Article XII). `credential_hint` carries the masked last-4
so the UI can show *which* key is configured without ever transporting it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import HealthStatus, ProviderType
from app.schemas.common import ORMModel

#: Provider types that are reached over a caller-supplied base_url rather than
#: the vendor's hosted endpoint.
_LOCAL_TYPES = {ProviderType.OLLAMA, ProviderType.VLLM}


class ProviderCreate(BaseModel):
    provider_type: ProviderType
    display_name: str = Field(min_length=1, max_length=200)
    #: Plaintext on write only; encrypted at rest, never returned.
    api_key: str | None = Field(default=None, max_length=500, repr=False)
    base_url: str | None = Field(default=None, max_length=500)
    #: Provider-specific extras (Azure endpoint/deployment name, AWS region).
    #: Stored inside the same encrypted blob as the API key.
    extra_credentials: dict[str, str] | None = Field(default=None, repr=False)
    #: Required when provider_type == CUSTOM; the plugin's manifest id
    #: (PluginRegistry). Ignored otherwise. Only presence is validated here —
    #: whether the id actually resolves in the live registry, and what that
    #: plugin's manifest requires (base_url/auth_type), is checked at the
    #: route layer (app/api/v1/providers.py), which is the only place that
    #: already holds a registry handle. Duplicating that lookup here would
    #: risk two different error shapes for the same failure.
    plugin_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _require_credentials_where_needed(self) -> ProviderCreate:
        if self.provider_type == ProviderType.CUSTOM:
            if not self.plugin_id:
                raise ValueError("plugin_id is required when provider_type is 'custom'")
            return self
        if self.provider_type in _LOCAL_TYPES:
            if not self.base_url:
                raise ValueError(
                    f"base_url is required for '{self.provider_type}' providers "
                    "(the local endpoint the gateway should call)"
                )
        elif not self.api_key:
            raise ValueError(
                f"api_key is required for '{self.provider_type}' providers"
            )
        return self


class ProviderUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=500, repr=False)
    base_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    extra_credentials: dict[str, str] | None = Field(default=None, repr=False)


class ProviderOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    provider_type: ProviderType
    display_name: str
    base_url: str | None = None
    is_active: bool
    health_status: HealthStatus
    last_health_check_at: datetime | None = None
    last_latency_ms: int | None = None
    created_at: datetime
    #: Masked, e.g. "********a1b2". Never the full key.
    credential_hint: str | None = None
    has_credentials: bool = False
    plugin_id: str | None = None


class ProviderModelCreate(BaseModel):
    model_id: str = Field(min_length=1, max_length=200)
    display_name: str | None = Field(default=None, max_length=200)
    context_window: int = Field(default=8192, ge=1)
    input_price_per_1m: Decimal | None = Field(default=None, ge=0)
    output_price_per_1m: Decimal | None = Field(default=None, ge=0)
    capabilities: list[str] = Field(default_factory=list)


class ProviderModelOut(ORMModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    model_id: str
    display_name: str
    context_window: int
    input_price_per_1m: Decimal | None = None
    output_price_per_1m: Decimal | None = None
    capabilities: list[str]
    is_available: bool


class ProviderHealthOut(BaseModel):
    provider_id: uuid.UUID
    health_status: HealthStatus
    latency_ms: int | None = None
    checked_at: datetime
    detail: str | None = None


class PluginManifestOut(BaseModel):
    """Response shape for `GET /providers/plugins` — 1:1 with
    `app.plugins.base.ProviderManifest`, exposed to the wizard's
    provider-type picker."""

    id: str
    display_name: str
    auth_type: Literal["api_key", "none", "bearer_token"]
    default_base_url: str | None
    requires_base_url: bool
    capabilities: list[str]
    pricing_hint: dict[str, Any] | None = None


class DiscoveredModelOut(BaseModel):
    model_id: str
    display_name: str
    context_window: int | None = None
    capabilities: list[str] = Field(default_factory=list)


class ModelDiscoveryOut(BaseModel):
    provider_id: uuid.UUID
    models: list[DiscoveredModelOut]


class BulkModelConfirm(BaseModel):
    """Wizard's final "confirm selected models" step — the user-reviewed
    subset of `ModelDiscoveryOut.models`, reusing the existing
    `ProviderModelCreate` shape per item."""

    models: list[ProviderModelCreate] = Field(min_length=1)
