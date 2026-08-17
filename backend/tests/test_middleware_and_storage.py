"""Cross-cutting middleware and upload-storage behaviour.

Like `test_app_contract.py`, these build the app without entering the lifespan,
so no Postgres or Redis is required: requests are driven through
`httpx.ASGITransport`, which skips startup/shutdown events.

Requests here are rejected at the rate-limit middleware or the auth dependency,
both of which run before anything touches a datastore.
"""

from __future__ import annotations

import os

import httpx
import pytest

from app.core.config import get_settings
from app.core.errors import PROBLEM_CONTENT_TYPE, StorageProblem
from app.main import create_app
from app.models.enums import DatasetFormat


def _client(app) -> httpx.AsyncClient:
    # `raise_app_exceptions=False` because requests that get *past* the rate
    # limiter reach the auth dependency, which opens a DB session there is no
    # Postgres for here. Those surface as 500s; what matters is that the
    # limiter rejects later calls before routing, without a datastore.
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


@pytest.fixture
def app_with_limit(monkeypatch):
    """An app whose rate limit is low enough to trip in a handful of calls."""
    monkeypatch.setenv("RATE_LIMIT_RPM", "3")
    get_settings.cache_clear()
    try:
        yield create_app()
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_rate_limit_returns_problem_json_with_retry_after(app_with_limit):
    headers = {"Authorization": "Bearer a-test-key"}
    async with _client(app_with_limit) as client:
        statuses = [
            (await client.get("/api/v1/providers", headers=headers)).status_code
            for _ in range(5)
        ]
        final = await client.get("/api/v1/providers", headers=headers)

    # The limit is 3/min, so later calls must be rejected.
    assert 429 in statuses
    assert final.status_code == 429
    assert final.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    # Middleware runs outside the exception handlers; it must still emit the
    # RFC 7807 body every other error path uses rather than a bare {"detail"}.
    body = final.json()
    assert body["status"] == 429
    assert body["title"] == "Too Many Requests"
    assert body["instance"] == "/api/v1/providers"
    assert int(final.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_rate_limit_does_not_apply_to_probes(app_with_limit):
    """A tripped limit must never take the liveness probe down with it."""
    headers = {"Authorization": "Bearer a-test-key"}
    async with _client(app_with_limit) as client:
        for _ in range(6):
            await client.get("/api/v1/providers", headers=headers)
        health = await client.get("/health")

    assert health.status_code == 200


@pytest.mark.asyncio
async def test_unauthenticated_requests_bypass_the_limiter(app_with_limit):
    """Buckets are keyed by API key; anonymous callers must not share one."""
    async with _client(app_with_limit) as client:
        statuses = [
            (await client.get("/api/v1/providers")).status_code for _ in range(6)
        ]

    assert 429 not in statuses
    assert all(s == 401 for s in statuses)


@pytest.mark.asyncio
async def test_security_headers_are_present(app_with_limit):
    async with _client(app_with_limit) as client:
        response = await client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Request-ID"]


def test_unwritable_upload_dir_raises_storage_problem(monkeypatch, tmp_path):
    """A misconfigured volume is a 503 an operator can act on, not a bare 500."""
    from app.services import dataset_service

    # A path whose parent is a regular file can never be created.
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv("BENCHMARK_UPLOAD_DIR", str(blocker / "uploads"))
    get_settings.cache_clear()
    try:
        with pytest.raises(StorageProblem) as excinfo:
            dataset_service.storage_path_for(
                __import__("uuid").uuid4(), DatasetFormat.CSV
            )
    finally:
        get_settings.cache_clear()

    assert excinfo.value.status_code == 503
    # The message must name the directory and the remedy.
    assert str(blocker / "uploads") in excinfo.value.detail
    assert "BENCHMARK_UPLOAD_DIR" in excinfo.value.detail


def test_writable_upload_dir_is_created(monkeypatch, tmp_path):
    from app.services import dataset_service

    target = tmp_path / "uploads"
    monkeypatch.setenv("BENCHMARK_UPLOAD_DIR", str(target))
    get_settings.cache_clear()
    try:
        path = dataset_service.storage_path_for(
            __import__("uuid").uuid4(), DatasetFormat.JSON
        )
        dataset_service.write_dataset(path, b'[{"a": 1}]')
    finally:
        get_settings.cache_clear()

    assert os.path.isdir(target)
    assert path.endswith(".json")
    with open(path, "rb") as handle:
        assert handle.read() == b'[{"a": 1}]'


def test_consumer_name_is_unique_per_process_unless_pinned():
    from app.services.request_ingest_service import _consumer_name

    # Sharing one name across uvicorn workers makes them share a Redis
    # pending-entries list, so each process must derive its own by default.
    assert _consumer_name("") == _consumer_name("")
    assert str(os.getpid()) in _consumer_name("")
    assert _consumer_name("  ") != "  "
    assert _consumer_name("backend-1") == "backend-1"
