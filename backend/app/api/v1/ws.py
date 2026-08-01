"""WebSocket hub (T013).

One connection, many topic subscriptions (api-contracts.md 4) — a dashboard
with a dozen live widgets holds one socket, not twelve.

Fan-out goes through Redis Pub/Sub with channel names identical to topic names,
so any process (another `backend` replica, a Celery worker) can publish without
holding the socket (ARCHITECTURE.md 4.2). Alpha runs one replica; building it
this way costs nothing now and is what makes horizontal scaling additive later.

Protocol
--------
    client -> server   {"action": "subscribe",   "topic": "dashboard"}
                       {"action": "unsubscribe", "topic": "dashboard"}
                       {"action": "ping"}
    server -> client   {"topic": ..., "event": ..., "data": {...}}
                       {"topic": "_control", "event": "subscribed"|"error", ...}

Topics: `dashboard`, `deployments`, `routing`, `benchmark:{run_id}`,
`deployment:{deployment_id}:logs`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from redis.asyncio.client import PubSub

from app.core.redis import get_redis
from app.core.db import get_session_factory
from app.repositories.tenancy import APIKeyRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

#: Topics a client may subscribe to. An open subscribe would let a client
#: attach to any Redis channel in the process, including ones carrying other
#: projects' data.
_TOPIC_PATTERNS = (
    re.compile(r"^dashboard$"),
    re.compile(r"^deployments$"),
    re.compile(r"^routing$"),
    re.compile(r"^benchmark:[0-9a-fA-F-]{36}$"),
    re.compile(r"^deployment:[0-9a-fA-F-]{36}:logs$"),
)

MAX_TOPICS_PER_CONNECTION = 24


def is_valid_topic(topic: str) -> bool:
    return any(pattern.match(topic) for pattern in _TOPIC_PATTERNS)


class TopicSubscription:
    """Owns one Redis pubsub handle and the relay task feeding a socket."""

    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.pubsub: PubSub = get_redis().pubsub()
        self.topics: set[str] = set()
        self._relay: asyncio.Task[None] | None = None

    async def subscribe(self, topic: str) -> None:
        if topic in self.topics:
            return
        await self.pubsub.subscribe(topic)
        self.topics.add(topic)
        if self._relay is None:
            self._relay = asyncio.create_task(self._pump())

    async def unsubscribe(self, topic: str) -> None:
        if topic not in self.topics:
            return
        await self.pubsub.unsubscribe(topic)
        self.topics.discard(topic)

    async def _pump(self) -> None:
        """Relay Redis messages to the socket until the connection closes."""
        try:
            async for message in self.pubsub.listen():
                if message.get("type") != "message":
                    continue
                await self.websocket.send_text(message["data"])
        except (WebSocketDisconnect, RuntimeError):
            return
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - one socket dying is not a server error
            logger.exception("WebSocket relay failed; closing subscription pump.")

    async def close(self) -> None:
        if self._relay is not None:
            self._relay.cancel()
            try:
                await self._relay
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        try:
            if self.topics:
                await self.pubsub.unsubscribe(*self.topics)
            await self.pubsub.aclose()
        except Exception:  # noqa: BLE001 - teardown must not raise
            logger.debug("Error while closing pubsub", exc_info=True)


async def _authenticate(token: str | None) -> bool:
    """Validate the project API key passed as a query parameter.

    Browsers cannot set headers on a WebSocket handshake, so the key travels as
    `?token=`. That is the standard workaround and the reason the topic
    allowlist above exists: query strings land in access logs more readily than
    headers do, so a leaked token must not also be a key to arbitrary channels.
    """
    if not token:
        return False
    factory = get_session_factory()
    async with factory() as session:
        return await APIKeyRepository(session).resolve(token) is not None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, token: str | None = Query(None)
) -> None:
    if not await _authenticate(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    subscription = TopicSubscription(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _control(websocket, "error", {"detail": "malformed JSON"})
                continue

            action = message.get("action")
            topic = message.get("topic", "")

            if action == "ping":
                await _control(websocket, "pong", {})
                continue

            if action not in ("subscribe", "unsubscribe"):
                await _control(
                    websocket,
                    "error",
                    {"detail": f"unknown action '{action}'"},
                )
                continue

            if not is_valid_topic(topic):
                await _control(
                    websocket, "error", {"detail": f"invalid topic '{topic}'"}
                )
                continue

            if action == "subscribe":
                if len(subscription.topics) >= MAX_TOPICS_PER_CONNECTION:
                    await _control(
                        websocket,
                        "error",
                        {
                            "detail": "topic subscription limit reached "
                            f"({MAX_TOPICS_PER_CONNECTION})"
                        },
                    )
                    continue
                await subscription.subscribe(topic)
                await _control(websocket, "subscribed", {"topic": topic})
            else:
                await subscription.unsubscribe(topic)
                await _control(websocket, "unsubscribed", {"topic": topic})

    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected.")
    finally:
        await subscription.close()


async def _control(websocket: WebSocket, event: str, data: dict) -> None:
    await websocket.send_text(
        json.dumps({"topic": "_control", "event": event, "data": data})
    )
