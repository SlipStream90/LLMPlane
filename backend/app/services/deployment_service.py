"""Local model deployment control (T019).

SECURITY POSTURE — read before changing anything in this file
--------------------------------------------------------------------------
ARCHITECTURE.md 4.5 names deployment control as the highest-blast-radius
surface in the system, and backlog task T012 gates implementation on a security
review of the Docker-socket access pattern. **T012 had not been resolved when
this was written**, so this module is deliberately built to the most restrictive
reading of the architecture, and the review can only relax it, never discover
that it was already too permissive:

1. **`backend` never touches the Docker socket.** It validates, records state,
   and enqueues a Celery task. Only `workers` — which already requires Docker
   and GPU access to launch vLLM/Ollama at all — holds the socket. That keeps
   the internet-facing HTTP process out of the trust boundary entirely.
2. **No image name ever comes from a request body.** `IMAGE_TEMPLATES` below is
   the complete set of launchable images. `model_ref` is passed as an
   *argument* to one of them and is character-restricted at the schema layer
   (`schemas/deployment.py`).
3. **Log streaming does not need Docker either**: workers publish log lines to
   the Redis topic `deployment:{id}:logs`, and the SSE endpoint here relays
   from Redis.

Any change that gives `backend` direct Docker access, or that lets a caller
influence the image, must go back through T012.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictProblem, NotFoundProblem, ValidationProblem
from app.core.redis import get_redis, publish_event
from app.models.deployment import Deployment
from app.models.enums import (
    DeploymentBackend,
    DeploymentStatus,
    HealthStatus,
    ProviderType,
)
from app.models.provider import Provider
from app.repositories.deployment import DeploymentRepository
from app.repositories.provider import ProviderRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageTemplate:
    """An allow-listed launchable image. Pinned tags are resolved at build time
    by the worker, which re-checks PyPI/registry state — methodology_brief.md
    flags vLLM 0.26.0 as reported-yanked, so a hardcoded tag here would be a
    trap."""

    image: str
    #: Container port the served OpenAI-compatible API listens on.
    container_port: int
    requires_gpu: bool


#: THE COMPLETE SET OF LAUNCHABLE IMAGES. Adding an entry is a security change.
#: Hugging Face TGI is intentionally absent: the repo was archived read-only on
#: 2026-03-21 and receives no security patches (methodology_brief.md 1.2).
IMAGE_TEMPLATES: dict[DeploymentBackend, ImageTemplate] = {
    DeploymentBackend.OLLAMA: ImageTemplate("ollama/ollama", 11434, requires_gpu=False),
    DeploymentBackend.VLLM: ImageTemplate("vllm/vllm-openai", 8000, requires_gpu=True),
}

#: Host port range deployments are allocated from.
PORT_RANGE_START = 11500
PORT_RANGE_END = 11600


class DeploymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.deployments = DeploymentRepository(session)
        self.providers = ProviderRepository(session)

    # -- creation ----------------------------------------------------------
    async def create(
        self,
        *,
        project_id: uuid.UUID,
        backend_type: DeploymentBackend,
        model_ref: str,
        gpu_index: int | None,
        gpu_available: bool,
    ) -> Deployment:
        """Record a pending deployment and allocate its port.

        Launching itself happens in a Celery task; this returns immediately
        with a `pending` row so the API can answer 202 (api-contracts.md).
        """
        template = IMAGE_TEMPLATES[backend_type]

        # Fail with a clear 422 rather than a confusing container-launch error
        # 30 seconds later (infrastructure.md 3).
        if template.requires_gpu and not gpu_available:
            raise ValidationProblem(
                f"'{backend_type}' deployments require an NVIDIA GPU, and none was "
                "detected on this host. Use the 'ollama' backend for CPU-only "
                "hosts.",
                {"backend_type": str(backend_type), "gpu_available": False},
            )

        existing = [
            d
            for d in await self.deployments.list_for_project(project_id)
            if d.model_ref == model_ref
            and d.backend_type == backend_type
            and d.status
            in (
                DeploymentStatus.PENDING,
                DeploymentStatus.DOWNLOADING,
                DeploymentStatus.RUNNING,
            )
        ]
        if existing:
            raise ConflictProblem(
                f"'{model_ref}' is already deployed on the '{backend_type}' backend.",
                {"deployment_id": str(existing[0].id)},
            )

        port = await self._allocate_port()
        provider = await self._ensure_local_provider(project_id, backend_type, port)

        deployment = await self.deployments.add(
            Deployment(
                project_id=project_id,
                provider_id=provider.id,
                backend_type=backend_type,
                model_ref=model_ref,
                status=DeploymentStatus.PENDING,
                gpu_index=gpu_index,
                port=port,
            )
        )
        await publish_event(
            "deployments",
            "deployment_created",
            {"deployment_id": str(deployment.id), "status": str(deployment.status)},
        )
        return deployment

    async def _allocate_port(self) -> int:
        used = await self.deployments.used_ports()
        for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
            if port not in used:
                return port
        raise ConflictProblem(
            "No free host port available for a new deployment "
            f"(range {PORT_RANGE_START}-{PORT_RANGE_END} is exhausted). Stop or "
            "delete an existing deployment first."
        )

    async def _ensure_local_provider(
        self, project_id: uuid.UUID, backend_type: DeploymentBackend, port: int
    ) -> Provider:
        """Every deployment is registered under an `ollama`/`vllm` Provider row
        so gateway routing treats local and cloud models uniformly
        (data-models.md `Deployment.provider_id`)."""
        provider_type = (
            ProviderType.OLLAMA
            if backend_type is DeploymentBackend.OLLAMA
            else ProviderType.VLLM
        )
        display_name = f"Local {backend_type.value} :{port}"
        return await self.providers.add(
            Provider(
                project_id=project_id,
                provider_type=provider_type,
                display_name=display_name,
                base_url=f"http://host.docker.internal:{port}",
                is_active=True,
                health_status=HealthStatus.UNKNOWN,
            )
        )

    # -- lifecycle transitions --------------------------------------------
    async def get_or_404(
        self, deployment_id: uuid.UUID, project_id: uuid.UUID
    ) -> Deployment:
        deployment = await self.deployments.get(deployment_id, project_id=project_id)
        if deployment is None:
            raise NotFoundProblem("Deployment", deployment_id)
        return deployment

    async def mark_stopping(self, deployment: Deployment) -> Deployment:
        if deployment.status is DeploymentStatus.STOPPED:
            raise ConflictProblem("Deployment is already stopped.")
        return deployment

    async def mark_deleted(self, deployment: Deployment) -> None:
        await self.deployments.delete(deployment)

    # -- logs --------------------------------------------------------------
    async def stream_logs(self, deployment_id: uuid.UUID) -> AsyncIterator[str]:
        """Relay container log lines from Redis as SSE payloads.

        `workers` owns the Docker log stream and publishes each line to
        `deployment:{id}:logs`; `backend` only ever sees Redis. Yields raw
        payload strings — the route wraps them in SSE framing.
        """
        topic = f"deployment:{deployment_id}:logs"
        pubsub = get_redis().pubsub()
        await pubsub.subscribe(topic)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                yield message["data"]
        finally:
            await pubsub.unsubscribe(topic)
            await pubsub.aclose()
