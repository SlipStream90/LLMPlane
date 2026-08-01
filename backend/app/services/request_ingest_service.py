"""Gateway request-completion ingest (T018, ADR-004).

The gateway never writes Postgres on the inference hot path. It appends a
compact completion event to a Redis Stream; this consumer — a background task
started in the app lifespan — drains the stream, persists `Request` rows and
publishes the dashboard WebSocket delta.

Consequences the rest of the system must respect (stated plainly per Article
IX): dashboard/leaderboard/cost numbers are **eventually consistent**, usually
sub-second behind the gateway. If `backend` is down, completions still succeed
and this consumer catches up from the stream afterwards. Nothing downstream may
assume a `Request` row exists the instant a completion returns.

--------------------------------------------------------------------------
EVENT CONTRACT — `requests:completed`
--------------------------------------------------------------------------
The gateway's LiteLLM success/failure callback (owned by `gateway/`, T003)
must XADD a flat string map with these fields. Unknown fields are ignored;
missing optional fields default as noted.

    event_id          str   REQUIRED, unique per completion (idempotency key)
    project_id        uuid  optional; resolved from api_key_prefix if absent
    api_key_prefix    str   optional; first 8 chars of the caller's key
    routing_policy_id uuid  optional
    provider_id       uuid  optional
    model_id          str   REQUIRED
    status            str   success | error | timeout   (default: success)
    input_tokens      int   default 0
    output_tokens     int   default 0
    cost_usd          float default 0
    latency_ms        int   default 0
    ttft_ms           int   optional
    error_message     str   optional
    trace_id          str   optional — the OTel/Langfuse trace id
    tags              str   optional JSON array, e.g. '["playground"]'
    requested_at      str   optional ISO-8601; defaults to ingest time

Delivery is at-least-once. De-duplication is by unique index on
`request.event_id`, not by trusting the broker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from redis.exceptions import RedisError, ResponseError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.redis import get_redis, publish_event
from app.models.enums import RequestStatus
from app.models.request import Request
from app.repositories.request import RequestRepository
from app.repositories.tenancy import APIKeyRepository, ProjectRepository

logger = logging.getLogger(__name__)

#: How long XREADGROUP blocks before looping (ms). Bounded so the task can
#: observe cancellation promptly on shutdown.
_BLOCK_MS = 5000
_BATCH = 100


class RequestIngestService:
    """Parses and persists gateway completion events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.requests = RequestRepository(session)
        self.api_keys = APIKeyRepository(session)
        self.projects = ProjectRepository(session)

    async def ingest(self, event_id: str, fields: dict[str, Any]) -> Request | None:
        """Persist one event. Returns None when it was a duplicate or could not
        be attributed to a project."""
        stream_event_id = str(fields.get("event_id") or event_id)

        if await self.requests.exists_event(stream_event_id):
            return None  # at-least-once replay, already stored

        project_id = await self._resolve_project(fields)
        if project_id is None:
            # Unattributable events are acked, not retried forever: without a
            # project there is no tenant to bill or display them under. Logged
            # at warning so it is visible rather than silently dropped.
            logger.warning(
                "Dropping gateway completion event %s: no project could be "
                "resolved (project_id and api_key_prefix both absent/unknown).",
                stream_event_id,
            )
            return None

        request = Request(
            project_id=project_id,
            api_key_id=await self._resolve_api_key_id(fields),
            routing_policy_id=_uuid_or_none(fields.get("routing_policy_id")),
            provider_id=_uuid_or_none(fields.get("provider_id")),
            model_id=str(fields.get("model_id") or "unknown"),
            status=_status(fields.get("status")),
            input_tokens=_int(fields.get("input_tokens")),
            output_tokens=_int(fields.get("output_tokens")),
            cost_usd=_decimal(fields.get("cost_usd")),
            latency_ms=_int(fields.get("latency_ms")),
            ttft_ms=_int_or_none(fields.get("ttft_ms")),
            error_message=_truncate(fields.get("error_message"), 2000),
            trace_id=_truncate(fields.get("trace_id"), 64),
            tags=_tags(fields.get("tags")),
            event_id=stream_event_id,
            requested_at=_timestamp(fields.get("requested_at")),
        )
        try:
            return await self.requests.add(request)
        except IntegrityError:
            # Two consumers raced on the same event; the unique index won.
            await self.session.rollback()
            return None

    async def _resolve_project(self, fields: dict[str, Any]) -> uuid.UUID | None:
        explicit = _uuid_or_none(fields.get("project_id"))
        if explicit is not None:
            return explicit

        prefix = fields.get("api_key_prefix")
        if prefix:
            keys = await self.api_keys.list_all()
            for key in keys:
                if key.key_prefix == prefix and key.revoked_at is None:
                    return key.project_id
        return None

    async def _resolve_api_key_id(self, fields: dict[str, Any]) -> uuid.UUID | None:
        prefix = fields.get("api_key_prefix")
        if not prefix:
            return _uuid_or_none(fields.get("api_key_id"))
        for key in await self.api_keys.list_all():
            if key.key_prefix == prefix and key.revoked_at is None:
                return key.id
        return None


async def _publish_delta(request: Request) -> None:
    """Push the live dashboard delta for one persisted request."""
    await publish_event(
        "dashboard",
        "request_completed",
        {
            "project_id": str(request.project_id),
            "model_id": request.model_id,
            "status": str(request.status),
            "cost_usd": float(request.cost_usd),
            "latency_ms": request.latency_ms,
            "input_tokens": request.input_tokens,
            "output_tokens": request.output_tokens,
            "requested_at": request.requested_at.isoformat(),
        },
    )


async def ensure_consumer_group() -> None:
    """Create the stream + consumer group if absent. Idempotent."""
    settings = get_settings()
    redis = get_redis()
    try:
        await redis.xgroup_create(
            settings.requests_stream_key,
            settings.requests_consumer_group,
            id="0",
            mkstream=True,
        )
        logger.info(
            "Created Redis consumer group '%s' on stream '%s'.",
            settings.requests_consumer_group,
            settings.requests_stream_key,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def consume_forever(stop_event: asyncio.Event | None = None) -> None:
    """Background consumer loop, started from the app lifespan.

    Errors are logged and retried with a backoff rather than killing the task —
    a Redis blip must not permanently stop request ingest, and a silently dead
    consumer is the worst failure mode here (the dashboard would just look
    quiet).
    """
    settings = get_settings()
    redis = get_redis()
    factory = get_session_factory()
    backoff = 1.0

    await ensure_consumer_group()
    logger.info(
        "Request ingest consumer started (stream=%s group=%s consumer=%s).",
        settings.requests_stream_key,
        settings.requests_consumer_group,
        settings.requests_consumer_name,
    )

    while not (stop_event and stop_event.is_set()):
        try:
            batches = await redis.xreadgroup(
                groupname=settings.requests_consumer_group,
                consumername=settings.requests_consumer_name,
                streams={settings.requests_stream_key: ">"},
                count=_BATCH,
                block=_BLOCK_MS,
            )
            backoff = 1.0
            if not batches:
                continue

            for _stream, messages in batches:
                for message_id, fields in messages:
                    persisted = None
                    try:
                        async with factory() as session:
                            service = RequestIngestService(session)
                            persisted = await service.ingest(message_id, fields)
                            await session.commit()
                    except Exception:  # noqa: BLE001 - one bad event, not the loop
                        logger.exception(
                            "Failed to ingest gateway completion event %s; "
                            "acknowledging to avoid a poison-message stall.",
                            message_id,
                        )
                    finally:
                        await redis.xack(
                            settings.requests_stream_key,
                            settings.requests_consumer_group,
                            message_id,
                        )
                    if persisted is not None:
                        await _publish_delta(persisted)

        except asyncio.CancelledError:
            logger.info("Request ingest consumer cancelled; shutting down.")
            raise
        except RedisError:
            logger.exception(
                "Redis error in request ingest consumer; retrying in %.0fs.", backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)


# ---------------------------------------------------------------------------
# Field coercion. Redis Stream fields are always strings; nothing here trusts
# the shape of an incoming value.
# ---------------------------------------------------------------------------
def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _status(value: Any) -> RequestStatus:
    try:
        return RequestStatus(str(value or "success"))
    except ValueError:
        return RequestStatus.ERROR


def _tags(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    try:
        parsed = json.loads(value)
        return [str(v) for v in parsed] if isinstance(parsed, list) else [str(value)]
    except (json.JSONDecodeError, TypeError):
        return [str(value)]


def _timestamp(value: Any) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _truncate(value: Any, limit: int) -> str | None:
    if value in (None, ""):
        return None
    return str(value)[:limit]
