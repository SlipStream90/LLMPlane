"""Local deployment schemas (PRD 3.2)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import DeploymentBackend, DeploymentStatus
from app.schemas.common import ORMModel

#: A model reference is an image *argument*, never an image name. Restricting
#: it to the character set real HF/Ollama tags use keeps shell/API
#: metacharacters out of anything that reaches the Docker Engine API
#: (ARCHITECTURE.md 4.5). The allow-listed image templates themselves live in
#: services/deployment_service.py.
_MODEL_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,299}$")


class DeploymentCreate(BaseModel):
    backend_type: DeploymentBackend
    model_ref: str = Field(min_length=1, max_length=300)
    gpu_index: int | None = Field(default=None, ge=0, le=15)
    config: dict | None = Field(
        default=None,
        description="Operator-supplied launch/runtime configuration (context "
        "length, quantization, batch size, health checks, …).",
    )

    @field_validator("model_ref")
    @classmethod
    def _validate_model_ref(cls, v: str) -> str:
        v = v.strip()
        if not _MODEL_REF_RE.match(v):
            raise ValueError(
                "model_ref may contain only letters, digits and . _ : / - "
                "characters (it is passed as an argument to an allow-listed image)"
            )
        return v


class DeploymentOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    provider_id: uuid.UUID
    backend_type: DeploymentBackend
    model_ref: str
    status: DeploymentStatus
    container_id: str | None = None
    gpu_index: int | None = None
    port: int | None = None
    error_message: str | None = None
    download_progress_pct: int | None = None
    config: dict | None = None
    created_at: datetime


class GpuTelemetrySampleOut(ORMModel):
    sampled_at: datetime
    gpu_index: int
    gpu_util_pct: float
    vram_used_mb: int
    vram_total_mb: int
    cpu_util_pct: float | None = None
    ram_used_mb: int | None = None
