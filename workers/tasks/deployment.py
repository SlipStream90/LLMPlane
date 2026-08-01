"""Local model deployment lifecycle (T020).

This module is the *only* place in the system that talks to the Docker Engine
API. The API container never does (see
backend/app/services/deployment_service.py for the full rationale and the T012
security-review gate).

Hard rules, enforced here rather than trusted from the caller:
  * the image comes from `IMAGE_TEMPLATES`, never from a request;
  * `model_ref` is passed as an argument/env value to that image;
  * `ollama serve` is always spelled out explicitly — since Ollama v0.32.0 a
    bare `ollama` starts an interactive agent shell, not the model server
    (methodology_brief.md 5, HIGH severity). A container entrypoint written
    from older documentation silently starts the wrong process.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import shared_task

from app.models.enums import DeploymentBackend, DeploymentStatus
from app.repositories.deployment import DeploymentRepository
from workers.db import run_async, session_scope
from workers.notify import publish
from workers.tracing import internal_span

logger = logging.getLogger(__name__)

#: Mirrors backend/app/services/deployment_service.IMAGE_TEMPLATES. Kept as an
#: independent constant on purpose: the worker must not be able to launch an
#: image just because the API asked it to.
ALLOWED_IMAGES: dict[DeploymentBackend, str] = {
    DeploymentBackend.OLLAMA: "ollama/ollama",
    DeploymentBackend.VLLM: "vllm/vllm-openai",
}

#: Image tags are configurable because pinning them in code has already bitten
#: this ecosystem: vLLM 0.26.0 was reported yanked days after release
#: (methodology_brief.md 5). Operators set these to a verified-current tag at
#: deploy time.
DEFAULT_TAGS: dict[DeploymentBackend, str] = {
    DeploymentBackend.OLLAMA: "latest",
    DeploymentBackend.VLLM: "latest",
}

CONTAINER_LABEL = "dev.llmplane.deployment_id"


def _docker_client():
    """Import and connect lazily so a worker without Docker can still run
    non-deployment tasks."""
    import docker

    return docker.from_env()


def _image_for(backend: DeploymentBackend) -> str:
    import os

    tag = os.getenv(f"LLMPLANE_{backend.value.upper()}_IMAGE_TAG", DEFAULT_TAGS[backend])
    return f"{ALLOWED_IMAGES[backend]}:{tag}"


@shared_task(name="workers.tasks.deployment.start_local_model", bind=True, max_retries=0)
def start_local_model(self, deployment_id: str) -> dict[str, Any]:  # noqa: ANN001
    """Launch the container for a pending deployment."""
    return run_async(lambda: _start(uuid.UUID(deployment_id)))


async def _start(deployment_id: uuid.UUID) -> dict[str, Any]:
    async with session_scope() as session:
        repo = DeploymentRepository(session)
        deployment = await repo.get(deployment_id)
        if deployment is None:
            logger.warning("start_local_model: deployment %s no longer exists", deployment_id)
            return {"status": "missing", "deployment_id": str(deployment_id)}

        backend = deployment.backend_type
        image = _image_for(backend)
        model_ref = deployment.model_ref
        port = deployment.port
        gpu_index = deployment.gpu_index

    with internal_span(
        "deployment.start", deployment_id=str(deployment_id), image=image
    ):
        try:
            client = _docker_client()
            template_port = 11434 if backend is DeploymentBackend.OLLAMA else 8000

            if backend is DeploymentBackend.OLLAMA:
                # `ollama serve` explicitly — never a bare `ollama` (see module
                # docstring).
                command = "serve"
                environment = {"OLLAMA_HOST": "0.0.0.0"}
                volumes = {"llmplane_ollama": {"bind": "/root/.ollama", "mode": "rw"}}
                device_requests = None
            else:
                command = [
                    "--model",
                    model_ref,
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(template_port),
                ]
                environment = {}
                volumes = {"llmplane_hf_cache": {"bind": "/root/.cache/huggingface", "mode": "rw"}}
                import docker.types

                device_requests = [
                    docker.types.DeviceRequest(
                        device_ids=[str(gpu_index)] if gpu_index is not None else None,
                        count=-1 if gpu_index is None else None,
                        capabilities=[["gpu"]],
                    )
                ]

            await _set_status(deployment_id, DeploymentStatus.DOWNLOADING)
            client.images.pull(image)

            container = client.containers.run(
                image,
                command=command,
                detach=True,
                name=f"llmplane-{backend.value}-{str(deployment_id)[:8]}",
                labels={CONTAINER_LABEL: str(deployment_id)},
                ports={f"{template_port}/tcp": port},
                environment=environment,
                volumes=volumes,
                device_requests=device_requests,
                restart_policy={"Name": "unless-stopped"},
            )

            if backend is DeploymentBackend.OLLAMA:
                # Ollama serves models on demand; pull the weights now so the
                # first gateway request is not a multi-minute download.
                exit_code, _ = container.exec_run(["ollama", "pull", model_ref])
                if exit_code != 0:
                    raise RuntimeError(
                        f"'ollama pull {model_ref}' failed inside the container "
                        f"(exit code {exit_code}). Check the model name."
                    )

            await _set_status(
                deployment_id,
                DeploymentStatus.RUNNING,
                container_id=container.id[:12],
                download_progress_pct=100,
            )
            return {"status": "running", "deployment_id": str(deployment_id)}

        except Exception as exc:  # noqa: BLE001 - recorded on the row, not swallowed
            logger.exception("Failed to start deployment %s", deployment_id)
            await _set_status(
                deployment_id, DeploymentStatus.ERROR, error_message=str(exc)[:2000]
            )
            return {"status": "error", "deployment_id": str(deployment_id), "error": str(exc)}


@shared_task(name="workers.tasks.deployment.stop_local_model")
def stop_local_model(deployment_id: str) -> dict[str, Any]:
    return run_async(lambda: _stop(uuid.UUID(deployment_id)))


async def _stop(deployment_id: uuid.UUID) -> dict[str, Any]:
    container_id = await _container_id_of(deployment_id)
    if container_id is None:
        await _set_status(deployment_id, DeploymentStatus.STOPPED)
        return {"status": "stopped", "detail": "no container was running"}

    try:
        client = _docker_client()
        container = client.containers.get(container_id)
        container.stop(timeout=30)
        await _set_status(deployment_id, DeploymentStatus.STOPPED)
        return {"status": "stopped", "deployment_id": str(deployment_id)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to stop deployment %s", deployment_id)
        await _set_status(deployment_id, DeploymentStatus.ERROR, error_message=str(exc)[:2000])
        return {"status": "error", "error": str(exc)}


@shared_task(name="workers.tasks.deployment.restart_local_model")
def restart_local_model(deployment_id: str) -> dict[str, Any]:
    stop_local_model(deployment_id)
    return start_local_model(deployment_id)  # type: ignore[call-arg]


@shared_task(name="workers.tasks.deployment.delete_local_model")
def delete_local_model(deployment_id: str, remove_volume: bool = False) -> dict[str, Any]:
    return run_async(lambda: _delete(uuid.UUID(deployment_id), remove_volume))


async def _delete(deployment_id: uuid.UUID, remove_volume: bool) -> dict[str, Any]:
    container_id = await _container_id_of(deployment_id)
    if container_id is not None:
        try:
            client = _docker_client()
            container = client.containers.get(container_id)
            container.remove(force=True, v=remove_volume)
        except Exception:  # noqa: BLE001 - a missing container must not block cleanup
            logger.warning(
                "Container %s could not be removed for deployment %s; deleting "
                "the row anyway.",
                container_id,
                deployment_id,
                exc_info=True,
            )

    async with session_scope() as session:
        repo = DeploymentRepository(session)
        deployment = await repo.get(deployment_id)
        if deployment is not None:
            await repo.delete(deployment)

    await publish(
        "deployments", "deployment_deleted", {"deployment_id": str(deployment_id)}
    )
    return {"status": "deleted", "deployment_id": str(deployment_id)}


@shared_task(name="workers.tasks.deployment.stream_container_logs")
def stream_container_logs(deployment_id: str, tail: int = 200) -> dict[str, Any]:
    """Pump container logs onto `deployment:{id}:logs` for the SSE endpoint.

    Bounded by `max_lines`: this task holds a worker slot while it streams, and
    an unbounded follow would occupy one forever.
    """
    return run_async(lambda: _stream_logs(uuid.UUID(deployment_id), tail))


async def _stream_logs(
    deployment_id: uuid.UUID, tail: int, max_lines: int = 5000
) -> dict[str, Any]:
    container_id = await _container_id_of(deployment_id)
    topic = f"deployment:{deployment_id}:logs"
    if container_id is None:
        await publish(topic, "log_line", {"line": "[no container running]"})
        return {"status": "no_container"}

    client = _docker_client()
    container = client.containers.get(container_id)
    sent = 0
    for raw in container.logs(stream=True, follow=True, tail=tail):
        line = raw.decode("utf-8", errors="replace").rstrip("\n")
        await publish(topic, "log_line", {"line": line})
        sent += 1
        if sent >= max_lines:
            await publish(
                topic,
                "log_line",
                {"line": f"[log stream truncated after {max_lines} lines]"},
            )
            break
    return {"status": "complete", "lines": sent}


@shared_task(name="workers.tasks.deployment.poll_container_health")
def poll_container_health() -> dict[str, Any]:
    """Celery beat: reconcile DB status with actual container state.

    Containers die for reasons the control plane never sees (OOM, host reboot).
    Without this the UI would keep showing a model as `running` indefinitely.
    """
    return run_async(_poll_health)


async def _poll_health() -> dict[str, Any]:
    try:
        client = _docker_client()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Docker is unavailable; skipping health poll: %s", exc)
        return {"status": "docker_unavailable"}

    checked = 0
    changed = 0
    async with session_scope() as session:
        repo = DeploymentRepository(session)
        deployments = await repo.list_all()
        for deployment in deployments:
            if deployment.container_id is None:
                continue
            checked += 1
            try:
                container = client.containers.get(deployment.container_id)
                running = container.status == "running"
            except Exception:  # noqa: BLE001 - container gone
                running = False

            desired = (
                DeploymentStatus.RUNNING if running else DeploymentStatus.STOPPED
            )
            if deployment.status is not desired and deployment.status not in (
                DeploymentStatus.PENDING,
                DeploymentStatus.DOWNLOADING,
            ):
                deployment.status = desired
                changed += 1
                await publish(
                    "deployments",
                    "deployment_status",
                    {"deployment_id": str(deployment.id), "status": desired.value},
                )
        await session.flush()

    return {"status": "ok", "checked": checked, "changed": changed}


# ---------------------------------------------------------------------------
async def _container_id_of(deployment_id: uuid.UUID) -> str | None:
    async with session_scope() as session:
        deployment = await DeploymentRepository(session).get(deployment_id)
        return deployment.container_id if deployment else None


async def _set_status(
    deployment_id: uuid.UUID,
    status: DeploymentStatus,
    *,
    container_id: str | None = None,
    error_message: str | None = None,
    download_progress_pct: int | None = None,
) -> None:
    async with session_scope() as session:
        repo = DeploymentRepository(session)
        deployment = await repo.get(deployment_id)
        if deployment is None:
            return
        deployment.status = status
        if container_id is not None:
            deployment.container_id = container_id
        if download_progress_pct is not None:
            deployment.download_progress_pct = download_progress_pct
        deployment.error_message = error_message
        await session.flush()

    await publish(
        "deployments",
        "deployment_status",
        {
            "deployment_id": str(deployment_id),
            "status": status.value,
            "error_message": error_message,
            "at": datetime.now(timezone.utc).isoformat(),
        },
    )
