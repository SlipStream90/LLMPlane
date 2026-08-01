"""Retention pruning (T025).

`request` and `gpu_sample` are the only two tables that actually accumulate
volume (data-models.md 3). A daily beat task trims both:

  * `request`    — older than `REQUEST_RETENTION_DAYS` (default 90)
  * `gpu_sample` — older than `GPU_SAMPLE_RETENTION_HOURS` (default 72)

Full trace detail beyond the request window lives in Langfuse, not Postgres, so
pruning here loses aggregate history but not per-trace forensics.

Deletion is chunked: one `DELETE` across 90 days of a busy table would hold a
long transaction and bloat WAL. Chunking keeps each statement short enough to
stay out of the way of live traffic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import shared_task
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.models.deployment import GpuSample
from app.models.request import Request
from workers.db import run_async, session_scope

logger = logging.getLogger(__name__)

CHUNK_SIZE = 5000
MAX_CHUNKS = 200


@shared_task(name="workers.tasks.retention.prune_old_rows")
def prune_old_rows() -> dict[str, Any]:
    return run_async(_prune)


async def _prune() -> dict[str, Any]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    request_cutoff = now - timedelta(days=settings.request_retention_days)
    sample_cutoff = now - timedelta(hours=settings.gpu_sample_retention_hours)

    requests_deleted = await _chunked_delete(Request, Request.requested_at, request_cutoff)
    samples_deleted = await _chunked_delete(GpuSample, GpuSample.sampled_at, sample_cutoff)

    logger.info(
        "Retention prune complete: %s request rows older than %s, %s gpu_sample "
        "rows older than %s.",
        requests_deleted,
        request_cutoff.isoformat(),
        samples_deleted,
        sample_cutoff.isoformat(),
    )
    return {
        "status": "ok",
        "requests_deleted": requests_deleted,
        "gpu_samples_deleted": samples_deleted,
        "request_cutoff": request_cutoff.isoformat(),
        "gpu_sample_cutoff": sample_cutoff.isoformat(),
    }


async def _chunked_delete(model, time_column, cutoff: datetime) -> int:
    total = 0
    for _ in range(MAX_CHUNKS):
        async with session_scope() as session:
            ids = (
                (
                    await session.execute(
                        select(model.id).where(time_column < cutoff).limit(CHUNK_SIZE)
                    )
                )
                .scalars()
                .all()
            )
            if not ids:
                return total
            result = await session.execute(delete(model).where(model.id.in_(ids)))
            total += int(result.rowcount or 0)

    logger.warning(
        "Retention prune for %s hit the %s-chunk ceiling (%s rows removed this "
        "run); the remainder will be removed on the next scheduled run.",
        model.__tablename__,
        MAX_CHUNKS,
        total,
    )
    return total
