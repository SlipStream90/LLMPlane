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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.v1 import ws as ws_module
from app.core.config import get_settings
from app.core.db import dispose_engine, init_engine
from app.core.errors import register_exception_handlers
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
    )

    # Restricted to the configured frontend origin(s); never "*"
    # (ARCHITECTURE.md 4.5).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
    async def ready() -> dict[str, object]:
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
        checks["ready"] = all(
            v == "ok" for k, v in checks.items() if k in ("database", "redis")
        )
        return checks

    return app


app = create_app()
