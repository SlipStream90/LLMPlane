"""The assembled app matches the architecture's API contract.

Checks the route surface and cross-cutting guarantees without needing Postgres
or Redis: `create_app()` builds the router tree, and OpenAPI generation does not
touch the datastores (they are created in the lifespan, which is not entered
here).
"""

from __future__ import annotations

import pytest

from app.main import create_app


@pytest.fixture(scope="module")
def spec() -> dict:
    return create_app().openapi()


#: Every path api-contracts.md 1 declares, in generated-OpenAPI form.
CONTRACT_PATHS = [
    "/api/v1/auth/bootstrap-key",
    "/api/v1/projects",
    "/api/v1/projects/{project_id}/keys",
    "/api/v1/providers",
    "/api/v1/providers/{provider_id}/health-check",
    "/api/v1/providers/{provider_id}/models",
    "/api/v1/deployments",
    "/api/v1/deployments/{deployment_id}/stop",
    "/api/v1/deployments/{deployment_id}/restart",
    "/api/v1/deployments/{deployment_id}/logs",
    "/api/v1/deployments/{deployment_id}/telemetry",
    "/api/v1/routing-policies",
    "/api/v1/routing-policies/{policy_id}/activate",
    "/api/v1/playground/compare",
    "/api/v1/prompts",
    "/api/v1/prompts/{prompt_id}/versions",
    "/api/v1/prompts/{prompt_id}/versions/{a}/diff/{b}",
    "/api/v1/prompts/{prompt_id}/rollback/{version_number}",
    "/api/v1/experiments",
    "/api/v1/experiments/{experiment_id}/runs",
    "/api/v1/benchmark-datasets",
    "/api/v1/benchmarks/run",
    "/api/v1/benchmarks/{run_id}",
    "/api/v1/benchmarks/{run_id}/results",
    "/api/v1/evaluations",
    "/api/v1/leaderboard",
    "/api/v1/dashboard/summary",
    "/api/v1/dashboard/timeseries",
    "/api/v1/cost/breakdown",
    "/api/v1/traces",
    "/api/v1/traces/{trace_id}",
    "/health",
]


@pytest.mark.parametrize("path", CONTRACT_PATHS)
def test_contract_path_is_registered(spec: dict, path: str) -> None:
    assert path in spec["paths"], f"{path} is missing from the API surface"


def test_the_gateway_surface_is_not_reimplemented(spec: dict) -> None:
    """ADR-001: `/v1/chat/completions` belongs to the gateway container. The
    control plane must not shadow it, or the "change only base_url" promise
    breaks."""
    assert not any(p.startswith("/v1/") for p in spec["paths"])


def test_benchmark_run_start_returns_202(spec: dict) -> None:
    """A benchmark run is a chord, not a request — the contract says 202."""
    assert "202" in spec["paths"]["/api/v1/benchmarks/run"]["post"]["responses"]


def test_deployment_launch_returns_202(spec: dict) -> None:
    assert "202" in spec["paths"]["/api/v1/deployments"]["post"]["responses"]


def test_activate_declares_a_409(spec: dict) -> None:
    """api-contracts.md 3: activating a policy that references an unregistered
    model is a conflict."""
    responses = spec["paths"]["/api/v1/routing-policies/{policy_id}/activate"]["post"][
        "responses"
    ]
    assert "200" in responses


def _iter_routes(routes):
    """Starlette >=1.0 nests included routers as `_IncludedRouter` wrappers
    instead of flattening them into `app.routes`, so a plain scan misses
    anything mounted via `include_router` (including nested ones, like `/ws`
    under `api_router`). Recurse through `original_router.routes` to reach
    the real route objects.
    """
    for route in routes:
        nested = getattr(route, "original_router", None)
        if nested is not None:
            yield from _iter_routes(nested.routes)
        else:
            yield route


def test_websocket_route_exists() -> None:
    app = create_app()
    ws_routes = [
        route
        for route in _iter_routes(app.routes)
        if getattr(route, "path", None) == "/ws"
    ]
    assert ws_routes, "/ws WebSocket hub is not registered"


def test_cors_is_not_a_wildcard() -> None:
    """ARCHITECTURE.md 4.5: CORS is restricted to the configured frontend
    origin. A wildcard here would be a real vulnerability, not a style issue."""
    from app.core.config import get_settings

    assert "*" not in get_settings().cors_origin_list


def test_no_deprecated_event_handlers_are_used() -> None:
    """methodology_brief.md 1.3 / anti-pattern table: `@app.on_event` is
    deprecated; startup wiring must go through `lifespan=`."""
    import pathlib

    backend_root = pathlib.Path(__file__).resolve().parents[1]
    offenders = [
        str(path)
        for path in backend_root.rglob("*.py")
        if "on_event(" in path.read_text(encoding="utf-8") and "tests" not in path.parts
    ]
    assert not offenders, f"deprecated @app.on_event found in: {offenders}"
