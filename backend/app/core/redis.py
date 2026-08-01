"""Redis client + pub/sub fan-out helpers.

One client for the whole process, created in the app lifespan. Redis carries
four distinct workloads in this system (ARCHITECTURE.md 4.4):

  * Celery broker/result backend (owned by workers, not touched here)
  * WebSocket pub/sub fan-out (`publish_event` below)
  * the gateway request-completion Stream (ADR-004, see request_ingest_service)
  * LiteLLM's own rate-limit/budget counters (owned by the gateway container)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None


def init_redis() -> Redis:
    """Create the process-wide Redis client. Idempotent."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            health_check_interval=30,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None


def get_redis() -> Redis:
    if _redis is None:
        init_redis()
    assert _redis is not None
    return _redis


async def publish_event(topic: str, event: str, data: dict[str, Any]) -> None:
    """Publish a WebSocket-shaped event onto the pub/sub channel named after
    the topic.

    The channel name *is* the topic string (`dashboard`, `benchmark:{id}`,
    `deployment:{id}:logs`) so any process — backend replica or Celery worker —
    can publish without holding the socket (ARCHITECTURE.md 4.2).

    Fail-open: a Redis hiccup must never take down the API call that triggered
    the notification. The failure is logged loudly, not swallowed silently
    (Article XIV).
    """
    payload = json.dumps({"topic": topic, "event": event, "data": data})
    try:
        await get_redis().publish(topic, payload)
    except Exception:  # noqa: BLE001 - deliberate fail-open on a notify path
        logger.warning(
            "Failed to publish event to Redis; live update dropped "
            "(topic=%s event=%s). API result is unaffected.",
            topic,
            event,
            exc_info=True,
        )
