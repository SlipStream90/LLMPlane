"""FastAPI application entrypoint (T004).

Startup/shutdown use the `lifespan=` async context manager. `@app.on_event` is
deprecated and appears nowhere in this codebase (methodology_brief.md 1.3).

Resources created once at startup and shared for the process lifetime: the
SQLAlchemy async engine, the Redis client, the OTel tracer provider, and the
Redis Streams request-ingest consumer task (ADR-004).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.api.v1 import ws as ws_module
from app.core.config import get_settings
from app.core.db import dispose_engine, init_engine
from app.core.errors import problem_response, register_exception_handlers
from app.core.logging import clear_request_context, configure_logging, set_request_context
from app.core.redis import close_redis, init_redis
from app.core.tracing import configure_tracing
from app.services.request_ingest_service import consume_forever

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_file)

    init_engine()
    init_redis()
    from app.plugins.registry import get_plugin_registry
    from app.services.gateway_client import GatewayClient

    await get_plugin_registry().discover(GatewayClient())
    tracing_enabled = configure_tracing(
        settings.otel_service_name, settings.otel_exporter_otlp_endpoint
    )
    app.state.tracing_enabled = tracing_enabled

    stop_event = asyncio.Event()
    consumer_task: asyncio.Task[None] | None = None
    if settings.enable_stream_consumer:
        consumer_task = asyncio.create_task(consume_forever(stop_event))
    else:
        logger.warning(
            "Request ingest consumer is DISABLED (ENABLE_STREAM_CONSUMER=false). "
            "Gateway traffic will not appear in the dashboard while it is off."
        )

    # In prod the CORS default is almost never right, and the failure mode is a
    # browser-side block with a healthy-looking backend — nothing in the server
    # log says why. Say it out loud at startup instead.
    if settings.environment == "prod":
        local_only = all(
            o.startswith(("http://localhost", "http://127.0.0.1"))
            for o in settings.cors_origin_list
        )
        if local_only:
            logger.warning(
                "CORS_ORIGINS is still %s in a prod environment. Browser requests "
                "from the deployed frontend will be blocked — set CORS_ORIGINS to "
                "the frontend's public origin.",
                settings.cors_origin_list,
            )

    logger.info(
        "%s startup complete (env=%s).", settings.app_name, settings.environment
    )
    try:
        yield
    finally:
        stop_event.set()
        if consumer_task is not None:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
        await close_redis()
        await get_plugin_registry().shutdown()
        await dispose_engine()
        logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0-alpha",
        description=(
            "Control-plane API for the LLM Control Plane. The OpenAI-compatible "
            "inference surface (POST /v1/chat/completions) is served by the "
            "gateway container, not by this service — see ADR-001."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
        openapi_tags=[
            {"name": "auth", "description": "Bootstrap authentication"},
            {"name": "providers", "description": "LLM provider management"},
            {"name": "deployments", "description": "Model deployment lifecycle"},
            {"name": "routing", "description": "Traffic routing policies"},
            {"name": "playground", "description": "Interactive model testing"},
            {"name": "prompts", "description": "Prompt version management"},
            {"name": "experiments", "description": "A/B experiments"},
            {"name": "benchmarks", "description": "Benchmark datasets and runs"},
            {"name": "evaluations", "description": "Model evaluation results"},
            {"name": "dashboard", "description": "Dashboard aggregates"},
            {"name": "cost-analytics", "description": "Cost analysis"},
            {"name": "logs", "description": "Structured log explorer"},
            {"name": "traces", "description": "OpenTelemetry traces"},
        ],
    )

    # Declare API key security scheme for Swagger UI
    app.openapi_schema = None  # Force regeneration with security

    _original_openapi = app.openapi

    def _openapi_with_security():
        if app.openapi_schema:
            return app.openapi_schema
        schema = _original_openapi()
        schema["components"] = schema.get("components", {})
        schema["components"]["securitySchemes"] = {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Bearer token: `Bearer <api_key>`",
            }
        }
        schema["security"] = [{"ApiKeyAuth": []}]
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = _openapi_with_security

    # Restricted to the configured frontend origin(s); never "*"
    # (ARCHITECTURE.md 4.5).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Rate limiting (per-API-key fixed window) ──────────────────────────
    # In-process, per-worker state: with N uvicorn workers the effective ceiling
    # is N × RATE_LIMIT_RPM. Adequate at alpha scale; a Redis sliding window is
    # the fix when the limit needs to be exact across processes.
    import hashlib
    import time

    _rate_buckets: dict[str, tuple[float, int]] = {}
    _last_sweep = 0.0
    _RATE_WINDOW_S = 60.0
    _RATE_LIMIT = settings.rate_limit_rpm
    _EXEMPT_PATHS = frozenset(
        {"/health", "/ready", "/docs", "/openapi.json", "/metrics"}
    )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        nonlocal _last_sweep

        if request.url.path in _EXEMPT_PATHS or _RATE_LIMIT <= 0:
            return await call_next(request)

        api_key = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not api_key:
            return await call_next(request)

        # Key the bucket by digest, not by the credential itself, so a heap dump
        # or a debugger frame does not hand over live API keys.
        bucket_key = hashlib.sha256(api_key.encode()).hexdigest()
        now = time.monotonic()

        window_start, count = _rate_buckets.get(bucket_key, (now, 0))
        if now - window_start > _RATE_WINDOW_S:
            window_start, count = now, 0

        if count >= _RATE_LIMIT:
            retry_after = max(1, int(_RATE_WINDOW_S - (now - window_start)))
            return problem_response(
                request,
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too Many Requests",
                f"Rate limit of {_RATE_LIMIT} requests/minute exceeded.",
                "https://llmplane.dev/problems/rate-limited",
                headers={"Retry-After": str(retry_after)},
            )

        _rate_buckets[bucket_key] = (window_start, count + 1)

        # Sweep on a timer, not on every request past an arbitrary size. The old
        # `if len(...) > 100` ran an O(n) scan on *every* request once the
        # process had seen 100 distinct keys.
        if now - _last_sweep > _RATE_WINDOW_S:
            _last_sweep = now
            for k in [
                k
                for k, (start, _) in _rate_buckets.items()
                if now - start > _RATE_WINDOW_S
            ]:
                del _rate_buckets[k]

        return await call_next(request)

    # ── Security headers ──────────────────────────────────────────────────
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.environment == "prod":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        """Tag every log line in the request scope and emit a structured
        request-completed line (PRD §43)."""
        import uuid

        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        trace_id = request.headers.get("x-trace-id")
        set_request_context(request_id=request_id, trace_id=trace_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
            },
        )
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(ws_module.router)

    # Prometheus scrape target (infrastructure.md 1). Optional so the app still
    # boots if the instrumentator package is absent in a slim test image.
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(
            app, endpoint="/metrics", include_in_schema=False
        )
    except ImportError:  # pragma: no cover - only in stripped environments
        logger.warning("prometheus_fastapi_instrumentator missing; /metrics disabled.")

    @app.get("/health", tags=["meta"], summary="Liveness probe")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["meta"], summary="Readiness probe")
    async def ready() -> JSONResponse:
        """Readiness reports each dependency separately.

        A single boolean would hide *which* dependency is down, which is the
        only thing the operator actually needs at 3am.
        """
        from sqlalchemy import text

        from app.core.db import get_session_factory
        from app.core.redis import get_redis

        checks: dict[str, object] = {}
        try:
            factory = get_session_factory()
            async with factory() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            checks["database"] = f"error: {exc}"

        try:
            await get_redis().ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {exc}"

        checks["tracing"] = (
            "enabled" if getattr(app.state, "tracing_enabled", False) else "disabled"
        )
        ready = all(
            v == "ok" for k, v in checks.items() if k in ("database", "redis")
        )
        checks["ready"] = ready
        # A readiness probe that answers 200 while a dependency is down is not a
        # readiness probe — the orchestrator keeps routing traffic to a process
        # that cannot serve it. The body still names which check failed.
        return JSONResponse(
            checks,
            status_code=(
                status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
        )

    return app


app = create_app()
