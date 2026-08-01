"""OpenTelemetry tracing helper — the ONLY module allowed to name raw
``gen_ai.*`` attribute strings.

Rationale (ARCHITECTURE.md 4.3, methodology_brief.md 1.7): the OTel GenAI
semantic conventions are still *experimental* as of 2026-03 and attribute names
are expected to churn. Every span in the system is created through this module,
so a convention rename is a one-file change instead of a repo-wide grep.

This file is mirrored verbatim at ``workers/tracing.py``. Keep the two copies
identical — they are one module living in two import roots (the backend package
and the worker package), which is the deliberate coupling ARCHITECTURE.md 3.2
already accepts for models/repositories.

Fail-open: if no OTLP endpoint is configured, tracing degrades to no-op spans.
The application must never fail because a telemetry backend is absent
(Article XIV) — but the degradation is logged at startup, loudly, once.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from collections.abc import Iterator
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanKind, Status, StatusCode

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# OTel GenAI semantic conventions (EXPERIMENTAL — see module docstring).
# Nothing outside this module may reference these strings.
# --------------------------------------------------------------------------
ATTR_SYSTEM = "gen_ai.system"
ATTR_OPERATION = "gen_ai.operation.name"
ATTR_REQUEST_MODEL = "gen_ai.request.model"
ATTR_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
ATTR_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
ATTR_RESPONSE_MODEL = "gen_ai.response.model"
ATTR_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
ATTR_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
ATTR_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

# Non-standard attributes this platform adds. Namespaced under `llmplane.` so
# they are never mistaken for upstream convention keys.
ATTR_COST_USD = "llmplane.cost_usd"
ATTR_LATENCY_MS = "llmplane.latency_ms"
ATTR_TTFT_MS = "llmplane.ttft_ms"
ATTR_PROJECT_ID = "llmplane.project_id"
ATTR_PROVIDER_ID = "llmplane.provider_id"
ATTR_ROUTING_POLICY_ID = "llmplane.routing_policy_id"
ATTR_ORIGIN = "llmplane.origin"  # playground | benchmark | experiment | api

_configured = False


def configure_tracing(
    service_name: str,
    endpoint: str | None = None,
) -> bool:
    """Install a global TracerProvider. Returns True if spans are exported.

    Idempotent — safe to call from both a FastAPI lifespan and a Celery
    worker-process init signal.
    """
    global _configured
    if _configured:
        return True

    endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.warning(
            "OTEL_EXPORTER_OTLP_ENDPOINT is not set — tracing is DISABLED for "
            "service '%s'. Traces will not reach Langfuse/Prometheus. This is a "
            "degraded mode, not an error.",
            service_name,
        )
        return False

    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        provider = TracerProvider(
            resource=Resource.create({"service.name": service_name})
        )
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces"))
        )
        trace.set_tracer_provider(provider)
        _configured = True
        logger.info("OTLP tracing enabled for '%s' -> %s", service_name, endpoint)
        return True
    except Exception:  # noqa: BLE001 - telemetry must not break the service
        logger.exception(
            "Failed to configure OTLP tracing for '%s'; continuing without "
            "traces (degraded).",
            service_name,
        )
        return False


def get_tracer(name: str = "llmplane") -> trace.Tracer:
    return trace.get_tracer(name)


@contextmanager
def llm_span(
    operation: str,
    *,
    system: str | None = None,
    request_model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    project_id: Any = None,
    provider_id: Any = None,
    routing_policy_id: Any = None,
    origin: str | None = None,
) -> Iterator[Span]:
    """Span for one model invocation.

    ``operation`` is the OTel GenAI operation name (``chat``, ``embeddings``).
    Call `record_llm_result` on the yielded span once the response is known.
    """
    attributes: dict[str, Any] = {ATTR_OPERATION: operation}
    _set(attributes, ATTR_SYSTEM, system)
    _set(attributes, ATTR_REQUEST_MODEL, request_model)
    _set(attributes, ATTR_REQUEST_TEMPERATURE, temperature)
    _set(attributes, ATTR_REQUEST_MAX_TOKENS, max_tokens)
    _set(attributes, ATTR_PROJECT_ID, _str(project_id))
    _set(attributes, ATTR_PROVIDER_ID, _str(provider_id))
    _set(attributes, ATTR_ROUTING_POLICY_ID, _str(routing_policy_id))
    _set(attributes, ATTR_ORIGIN, origin)

    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"{operation} {request_model or 'unknown'}",
        kind=SpanKind.CLIENT,
        attributes=attributes,
    ) as span:
        try:
            yield span
        except Exception as exc:  # noqa: BLE001 - re-raised after recording
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


@contextmanager
def internal_span(name: str, **attributes: Any) -> Iterator[Span]:
    """Span for non-LLM internal work (a Celery task, an aggregation query)."""
    tracer = get_tracer()
    clean = {k: v for k, v in attributes.items() if v is not None}
    with tracer.start_as_current_span(
        name, kind=SpanKind.INTERNAL, attributes=clean
    ) as span:
        try:
            yield span
        except Exception as exc:  # noqa: BLE001 - re-raised after recording
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


def record_llm_result(
    span: Span,
    *,
    response_model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
    ttft_ms: int | None = None,
    finish_reasons: list[str] | None = None,
    error: str | None = None,
) -> None:
    """Attach outcome attributes to an in-flight span."""
    if not span.is_recording():
        return
    _apply(span, ATTR_RESPONSE_MODEL, response_model)
    _apply(span, ATTR_USAGE_INPUT_TOKENS, input_tokens)
    _apply(span, ATTR_USAGE_OUTPUT_TOKENS, output_tokens)
    _apply(span, ATTR_COST_USD, cost_usd)
    _apply(span, ATTR_LATENCY_MS, latency_ms)
    _apply(span, ATTR_TTFT_MS, ttft_ms)
    if finish_reasons:
        span.set_attribute(ATTR_RESPONSE_FINISH_REASONS, finish_reasons)
    if error:
        span.set_status(Status(StatusCode.ERROR, error))
    else:
        span.set_status(Status(StatusCode.OK))


def current_trace_id() -> str | None:
    """Hex trace id of the active span, for correlating a `Request` row to its
    Langfuse trace (data-models.md `Request.trace_id`)."""
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x")


def _set(target: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        target[key] = value


def _apply(span: Span, key: str, value: Any) -> None:
    if value is not None:
        span.set_attribute(key, value)


def _str(value: Any) -> str | None:
    return None if value is None else str(value)
