"""Celery application (broker + result backend on Redis).

Queues are separated so a 400-item benchmark fan-out cannot starve a deployment
start/stop the user is waiting on:

  * ``default``     — provider health checks, retention pruning, telemetry
  * ``deployment``  — container lifecycle (user-interactive, must stay responsive)
  * ``benchmark``   — chord header/callback tasks
  * ``evaluation``  — metric scoring

Celery is the right task queue here specifically because chains/chords are
load-bearing: the benchmark fan-out is a canonical chord (parallel group +
aggregation callback). Lighter alternatives (arq, Dramatiq) have no Canvas
equivalent, which is why the methodology brief kept Celery (1.5).
"""

from __future__ import annotations

import logging
import os

from celery import Celery
from celery.signals import worker_process_init

logger = logging.getLogger(__name__)

BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery("llmplane", broker=BROKER_URL, backend=BROKER_URL)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    # A worker that dies mid-task must not have prefetched a queue's worth of
    # other work with it.
    worker_prefetch_multiplier=1,
    result_expires=60 * 60 * 24,
    task_default_queue="default",
    task_routes={
        "workers.tasks.deployment.*": {"queue": "deployment"},
        "workers.tasks.benchmark.*": {"queue": "benchmark"},
        "workers.tasks.evaluation.*": {"queue": "evaluation"},
    },
    beat_schedule={
        "poll-gpu-stats": {
            "task": "workers.tasks.telemetry.poll_gpu_stats",
            "schedule": float(os.getenv("GPU_POLL_INTERVAL_S", "15")),
        },
        "poll-container-health": {
            "task": "workers.tasks.deployment.poll_container_health",
            "schedule": 30.0,
        },
        "provider-health-sweep": {
            "task": "workers.tasks.telemetry.sweep_provider_health",
            "schedule": 300.0,
        },
        "prune-retention": {
            "task": "workers.tasks.retention.prune_old_rows",
            # Daily (data-models.md 3).
            "schedule": 60.0 * 60.0 * 24.0,
        },
    },
)

celery_app.autodiscover_tasks(
    [
        "workers.tasks.benchmark",
        "workers.tasks.deployment",
        "workers.tasks.evaluation",
        "workers.tasks.retention",
        "workers.tasks.telemetry",
    ],
    force=True,
)


@worker_process_init.connect
def _init_worker_process(**_: object) -> None:
    """Per-process init: tracing only.

    The database engine is created lazily per event loop in `workers/db.py` —
    creating it here would bind an asyncpg pool to a loop that no longer exists
    by the time a task runs.
    """
    from workers.tracing import configure_tracing

    configure_tracing(os.getenv("OTEL_SERVICE_NAME", "llmplane-workers"))
