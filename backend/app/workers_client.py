"""Thin Celery enqueue wrappers. No task bodies live here (ARCHITECTURE.md 3.1).

Tasks are dispatched **by name** with `send_task`, so `backend` never imports
`workers/` — the dependency runs one way only (workers import backend's models
and repositories, not the reverse). That keeps the API process free of RAGAS /
DeepEval / Docker / pynvml imports it has no use for.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from celery import Celery

from app.core.config import get_settings

# Task names. These strings are the contract with `workers/tasks/*`; a typo
# here is a task that silently never runs, so they are defined once.
TASK_START_LOCAL_MODEL = "workers.tasks.deployment.start_local_model"
TASK_STOP_LOCAL_MODEL = "workers.tasks.deployment.stop_local_model"
TASK_RESTART_LOCAL_MODEL = "workers.tasks.deployment.restart_local_model"
TASK_DELETE_LOCAL_MODEL = "workers.tasks.deployment.delete_local_model"
TASK_STREAM_LOGS = "workers.tasks.deployment.stream_container_logs"
TASK_POLL_CONTAINER_HEALTH = "workers.tasks.deployment.poll_container_health"
TASK_RUN_BENCHMARK = "workers.tasks.benchmark.launch_benchmark_run"
TASK_CHECK_PROVIDER_HEALTH = "workers.tasks.telemetry.check_provider_health"

QUEUE_DEFAULT = "default"
QUEUE_DEPLOYMENT = "deployment"
QUEUE_BENCHMARK = "benchmark"


@lru_cache
def get_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "llmplane-client", broker=settings.redis_url, backend=settings.redis_url
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    return app


def _send(name: str, queue: str, *args: Any, **kwargs: Any) -> str:
    result = get_celery().send_task(name, args=args, kwargs=kwargs, queue=queue)
    return result.id


def start_local_model(deployment_id: uuid.UUID) -> str:
    return _send(TASK_START_LOCAL_MODEL, QUEUE_DEPLOYMENT, str(deployment_id))


def stop_local_model(deployment_id: uuid.UUID) -> str:
    return _send(TASK_STOP_LOCAL_MODEL, QUEUE_DEPLOYMENT, str(deployment_id))


def restart_local_model(deployment_id: uuid.UUID) -> str:
    return _send(TASK_RESTART_LOCAL_MODEL, QUEUE_DEPLOYMENT, str(deployment_id))


def delete_local_model(deployment_id: uuid.UUID, *, remove_volume: bool = False) -> str:
    return _send(
        TASK_DELETE_LOCAL_MODEL,
        QUEUE_DEPLOYMENT,
        str(deployment_id),
        remove_volume=remove_volume,
    )


def stream_container_logs(deployment_id: uuid.UUID, *, tail: int = 200) -> str:
    """Ask a worker to pump this container's logs onto the
    `deployment:{id}:logs` Redis topic that the SSE endpoint relays."""
    return _send(TASK_STREAM_LOGS, QUEUE_DEPLOYMENT, str(deployment_id), tail=tail)


def launch_benchmark_run(benchmark_run_id: uuid.UUID) -> str:
    return _send(TASK_RUN_BENCHMARK, QUEUE_BENCHMARK, str(benchmark_run_id))


def check_provider_health(provider_id: uuid.UUID) -> str:
    return _send(TASK_CHECK_PROVIDER_HEALTH, QUEUE_DEFAULT, str(provider_id))
