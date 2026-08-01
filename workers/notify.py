"""Publishing WebSocket events from worker processes.

Workers publish to the same Redis channels the backend's `/ws` hub subscribes
to, so progress reaches the browser without the worker knowing anything about
sockets (ARCHITECTURE.md 4.2).

A separate client per call is deliberate: Celery forks, and a module-level
async Redis client bound to a dead event loop is a subtle, intermittent failure
mode. Publishing is infrequent enough that a fresh connection costs less than
that class of bug.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


async def publish(topic: str, event: str, data: dict[str, Any]) -> None:
    """Fail-open: a dropped notification must never fail the task itself."""
    payload = json.dumps({"topic": topic, "event": event, "data": data})
    client = Redis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
    )
    try:
        await client.publish(topic, payload)
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to publish '%s' on topic '%s'; live update dropped.",
            event,
            topic,
            exc_info=True,
        )
    finally:
        await client.aclose()


def publish_sync(topic: str, event: str, data: dict[str, Any]) -> None:
    """For synchronous task bodies that are not already inside `run_async`."""
    asyncio.run(publish(topic, event, data))
