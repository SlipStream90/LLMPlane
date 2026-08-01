"""Deployments API (T019): launch, stop, restart, delete, logs (SSE), telemetry.

Every mutating route here enqueues a Celery task and returns immediately —
`backend` holds no Docker socket (see services/deployment_service.py for the
full security rationale and the T012 gate).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse

from app import workers_client
from app.api.deps import ProjectDep, SessionDep
from app.core.errors import ConflictProblem
from app.models.enums import DeploymentStatus
from app.repositories.deployment import DeploymentRepository, GpuSampleRepository
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentOut,
    GpuTelemetrySampleOut,
)
from app.services.deployment_service import IMAGE_TEMPLATES, DeploymentService

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.get("", response_model=list[DeploymentOut], summary="List deployments")
async def list_deployments(
    session: SessionDep, project: ProjectDep
) -> list[DeploymentOut]:
    rows = await DeploymentRepository(session).list_for_project(project.id)
    return [DeploymentOut.model_validate(d) for d in rows]


@router.get(
    "/backends",
    summary="Launchable backends and whether this host can run them",
)
async def list_backends(session: SessionDep, project: ProjectDep) -> dict[str, object]:
    """Lets the UI disable vLLM up front on a CPU-only host instead of letting
    the user submit a launch that is guaranteed to 422."""
    gpu_available = await _gpu_available(session)
    return {
        "gpu_available": gpu_available,
        "backends": [
            {
                "backend_type": backend.value,
                "image": template.image,
                "requires_gpu": template.requires_gpu,
                "available": gpu_available or not template.requires_gpu,
            }
            for backend, template in IMAGE_TEMPLATES.items()
        ],
    }


@router.post(
    "",
    response_model=DeploymentOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Launch a local model deployment",
)
async def create_deployment(
    payload: DeploymentCreate, session: SessionDep, project: ProjectDep
) -> DeploymentOut:
    service = DeploymentService(session)
    deployment = await service.create(
        project_id=project.id,
        backend_type=payload.backend_type,
        model_ref=payload.model_ref,
        gpu_index=payload.gpu_index,
        gpu_available=await _gpu_available(session),
    )
    # Commit before enqueueing: a worker that picks the task up first must be
    # able to see the row.
    await session.commit()
    workers_client.start_local_model(deployment.id)
    return DeploymentOut.model_validate(deployment)


@router.post(
    "/{deployment_id}/stop", response_model=DeploymentOut, summary="Stop a deployment"
)
async def stop_deployment(
    deployment_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> DeploymentOut:
    service = DeploymentService(session)
    deployment = await service.get_or_404(deployment_id, project.id)
    if deployment.status is DeploymentStatus.STOPPED:
        raise ConflictProblem("Deployment is already stopped.")
    await session.commit()
    workers_client.stop_local_model(deployment.id)
    return DeploymentOut.model_validate(deployment)


@router.post(
    "/{deployment_id}/restart",
    response_model=DeploymentOut,
    summary="Restart a deployment",
)
async def restart_deployment(
    deployment_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> DeploymentOut:
    deployment = await DeploymentService(session).get_or_404(deployment_id, project.id)
    await session.commit()
    workers_client.restart_local_model(deployment.id)
    return DeploymentOut.model_validate(deployment)


@router.delete(
    "/{deployment_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete a deployment",
)
async def delete_deployment(
    deployment_id: uuid.UUID,
    session: SessionDep,
    project: ProjectDep,
    remove_volume: bool = Query(
        False, description="Also delete downloaded model weights."
    ),
) -> dict[str, str]:
    """Tear down the container, then the row.

    Deletion is asynchronous because the row must survive until the worker has
    actually removed the container — deleting it first would strand a running
    container with nothing tracking it.
    """
    await DeploymentService(session).get_or_404(deployment_id, project.id)
    await session.commit()
    workers_client.delete_local_model(deployment_id, remove_volume=remove_volume)
    return {"status": "accepted", "deployment_id": str(deployment_id)}


@router.get("/{deployment_id}/logs", summary="Stream container logs (SSE)")
async def stream_logs(
    deployment_id: uuid.UUID,
    session: SessionDep,
    project: ProjectDep,
    tail: int = Query(200, ge=1, le=5000),
) -> StreamingResponse:
    """Server-Sent Events, not a WebSocket: this is a one-way, one-shot stream
    and `EventSource` handles it natively (api-contracts.md 2)."""
    service = DeploymentService(session)
    deployment = await service.get_or_404(deployment_id, project.id)
    await session.commit()

    # Ask a worker to start pumping this container's logs into Redis; the
    # generator below relays whatever lands there.
    workers_client.stream_container_logs(deployment.id, tail=tail)

    async def event_source() -> AsyncIterator[bytes]:
        yield b": stream open\n\n"
        async for payload in service.stream_logs(deployment_id):
            yield f"data: {payload}\n\n".encode()

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/{deployment_id}/telemetry",
    response_model=list[GpuTelemetrySampleOut],
    summary="Recent GPU/CPU/VRAM samples",
)
async def deployment_telemetry(
    deployment_id: uuid.UUID,
    session: SessionDep,
    project: ProjectDep,
    minutes: int = Query(60, ge=1, le=4320),
) -> list[GpuTelemetrySampleOut]:
    await DeploymentService(session).get_or_404(deployment_id, project.id)
    samples = await GpuSampleRepository(session).recent_for_deployment(
        deployment_id, minutes=minutes
    )
    return [GpuTelemetrySampleOut.model_validate(s) for s in samples]


async def _gpu_available(session: SessionDep) -> bool:
    """Infer GPU presence from recent telemetry.

    The telemetry task writes `GpuSample` rows only when pynvml/nvidia-smi
    actually reports a device, so "a sample in the last hour" is a truthful
    proxy that costs one indexed query — and it degrades to `False` on a
    CPU-only host, which is the behaviour infrastructure.md 3 asks for.
    """
    return bool(
        await GpuSampleRepository(session).latest_host_samples(within_minutes=60)
    )
