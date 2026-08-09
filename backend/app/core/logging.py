"""Structured JSON logging (PRD §43).

Every log line is a single JSON object carrying the fields the Log Explorer
filters on — timestamp, level, service, request_id, trace_id, provider, model,
message — plus any ``extra`` the caller attaches. This makes logs machine
queryable instead of a wall of human-formatted text.

A contextvar carries request-scoped fields (request_id / trace_id) so every
line emitted while handling a request is tagged without callers threading them
through by hand. Provider/model are attached explicitly where they are known
(the gateway ingest path, provider health checks).
"""

from __future__ import annotations

import contextvars
import json
import logging
from datetime import datetime, timezone

# Fields carried on the request context and merged into every log line.
# `None` means "no context yet"; helpers treat it as an empty dict.
_REQUEST_CTX: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "llcp_request_ctx", default=None
)

# LogRecord attributes that are machinery, never payload.
_RESERVED = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "module", "msecs",
    "message", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
}


def set_request_context(**kwargs: object) -> None:
    """Merge request-scoped fields into the current context."""
    current = dict(_REQUEST_CTX.get() or {})
    current.update(kwargs)
    _REQUEST_CTX.set(current)


def clear_request_context() -> None:
    _REQUEST_CTX.set(None)


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ctx = _REQUEST_CTX.get() or {}
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "service": record.name or "application",
            "message": record.getMessage(),
        }
        for key in ("request_id", "trace_id", "provider", "model"):
            if ctx.get(key):
                payload[key] = ctx[key]
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(log_level: str, log_file: str | None = None) -> None:
    """Install the structured formatter on the root logger.

    Emits JSON to stdout (captured by the container/runtime) and, when
    ``log_file`` is set, also appends to that file — the file the Log Explorer
    reads via ``GET /logs``.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    formatter = StructuredFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handlers = [handler]

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except OSError as exc:  # pragma: no cover - environment dependent
            root.warning("Could not open LOG_FILE %s: %s", log_file, exc)

    root.handlers = handlers
    # Quiet the noisy default uvicorn access logger; request logging is handled
    # by our middleware instead.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
