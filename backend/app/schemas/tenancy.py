"""Project and API key schemas."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ApiKeyScope
from app.schemas.common import ORMModel

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not _SLUG_RE.match(v):
            raise ValueError(
                "slug must be lowercase alphanumeric words separated by single hyphens"
            )
        return v


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ProjectOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scopes: list[ApiKeyScope] = Field(default_factory=lambda: [ApiKeyScope.GATEWAY])
    rate_limit_rpm: int | None = Field(default=None, ge=1, le=1_000_000)
    quota_monthly_usd: Decimal | None = Field(default=None, ge=0)


class ApiKeyOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit_rpm: int | None = None
    quota_monthly_usd: Decimal | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    #: Raw secret. Returned exactly once, at creation, and never retrievable
    #: again — the server only stores its argon2id hash.
    key: str


class BootstrapKeyRequest(BaseModel):
    """First-key bootstrap (ADR-002 — alpha has no login flow).

    Authenticated by the `X-Bootstrap-Token` header against
    `BOOTSTRAP_ADMIN_TOKEN`, not by an API key (there isn't one yet).
    """

    project_name: str = Field(default="Default Project", min_length=1, max_length=200)
    project_slug: str = Field(default="default", min_length=1, max_length=120)
    key_name: str = Field(default="bootstrap-key", min_length=1, max_length=200)

    @field_validator("project_slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        v = v.strip().lower()
        if not _SLUG_RE.match(v):
            raise ValueError("project_slug must be a lowercase hyphenated slug")
        return v


class BootstrapKeyResponse(BaseModel):
    project: ProjectOut
    api_key: ApiKeyCreated
