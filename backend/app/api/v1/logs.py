"""Structured log query + live tail API (PRD §19–§25).

Reads newline-delimited JSON logs from ``LOG_FILE`` (each line matches the
structured schema in PRD §43: timestamp, level, service, request_id, trace_id,
provider, model, message, …). Absent or unwritable, the endpoints degrade to
empty results rather than failing — a missing log sink must not 500 the
observability surface (Article XIV).

Export (JSON / CSV / TXT / NDJSON) is performed client-side from the filtered
set the UI already holds, so the same filter powers both viewing and export.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/logs", tags=["logs"])

LOG_FILE = os.environ.get("LOG_FILE")


class LogEntryOut(BaseModel):
    timestamp: str | None = None
    level: str | None = None
    service: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    provider: str | None = None
    model: str | None = None
    message: str | None = None
    extra: dict = Field(default_factory=dict)


def _matches(entry: dict, filters: dict) -> bool:
    q = filters.get("q")
    if q:
        haystack = " ".join(str(v) for v in entry.values())
        if q.lower() not in haystack.lower():
            return False
    for key in ("level", "service", "provider", "model", "request_id", "trace_id"):
        if filters.get(key) and entry.get(key) != filters[key]:
            return False
    return True


def _read_entries(filters: dict, limit: int) -> list[dict]:
    if not LOG_FILE or not os.path.isfile(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return []

    out: list[dict] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            # Tolerate non-JSON lines as plain messages.
            entry = {"message": raw, "level": "INFO"}
        if _matches(entry, filters):
            out.append(entry)

    out.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    return out[:limit]


@router.get("", response_model=list[LogEntryOut], summary="Query structured logs")
async def query_logs(
    q: str | None = Query(None, description="Full-text search"),
    level: str | None = Query(None, description="DEBUG/INFO/WARNING/ERROR/CRITICAL"),
    service: str | None = Query(None),
    provider: str | None = Query(None),
    model: str | None = Query(None),
    request_id: str | None = Query(None, alias="request_id"),
    trace_id: str | None = Query(None, alias="trace_id"),
    limit: int = Query(500, ge=1, le=5000),
) -> list[LogEntryOut]:
    filters = {
        "q": q,
        "level": level,
        "service": service,
        "provider": provider,
        "model": model,
        "request_id": request_id,
        "trace_id": trace_id,
    }
    entries = _read_entries(filters, limit)
    return [LogEntryOut(**{k: v for k, v in e.items() if k in LogEntryOut.model_fields}) for e in entries]


@router.get("/stream", summary="Live tail of structured logs (SSE)")
async def stream_logs() -> StreamingResponse:
    """Server-Sent Events tail. Relays new lines appended to ``LOG_FILE`` and
    sends a heartbeat so proxies do not buffer/close the connection."""

    async def event_source() -> AsyncIterator[bytes]:
        yield b": stream open\n\n"
        inode = os.stat(LOG_FILE).st_ino if LOG_FILE and os.path.isfile(LOG_FILE) else None
        offset = os.path.getsize(LOG_FILE) if (LOG_FILE and os.path.isfile(LOG_FILE)) else 0
        last_heartbeat = time.time()
        while True:
            if not LOG_FILE or not os.path.isfile(LOG_FILE):
                if time.time() - last_heartbeat > 15:
                    yield b": heartbeat\n\n"
                    last_heartbeat = time.time()
                await _sleep(1)
                continue
            # File rotated under us: restart from the beginning.
            if os.stat(LOG_FILE).st_ino != inode:
                inode = os.stat(LOG_FILE).st_ino
                offset = 0
            with open(LOG_FILE, "r", encoding="utf-8") as fh:
                fh.seek(offset)
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    payload = raw if raw.startswith("{") else json.dumps({"message": raw})
                    yield f"data: {payload}\n\n".encode()
                offset = fh.tell()
            if time.time() - last_heartbeat > 15:
                yield b": heartbeat\n\n"
                last_heartbeat = time.time()
            await _sleep(1)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
