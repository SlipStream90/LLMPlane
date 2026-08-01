"""`anthropic` reference plugin (ARCHITECTURE.md §5.3, stretch).

Demonstrates the interface isn't OpenAI-shaped-only: Anthropic's `/v1/models`
uses `x-api-key` + `anthropic-version` headers rather than a bearer token —
the same headers `provider_health_service._auth_headers` already builds for
`ProviderType.ANTHROPIC`, reused here rather than re-derived.
`chat_completion`/`stream` are NOT overridden — they inherit the
`ProviderPlugin` defaults, which delegate to `GatewayClient` (ADR-002).
"""

from __future__ import annotations

import time

import httpx

from app.plugins.base import DiscoveredModel, PluginHealthResult, ProviderPlugin

_DEFAULT_BASE_URL = "https://api.anthropic.com"
_ANTHROPIC_VERSION = "2023-06-01"


def _headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"x-api-key": api_key, "anthropic-version": _ANTHROPIC_VERSION}


class AnthropicPlugin(ProviderPlugin):
    async def health_check(
        self, *, base_url: str | None, api_key: str | None, timeout_s: float = 10.0
    ) -> PluginHealthResult:
        target = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as http:
                response = await http.get(
                    f"{target}/v1/models", headers=_headers(api_key)
                )
            latency_ms = int((time.perf_counter() - started) * 1000)
            if response.status_code == 200:
                return PluginHealthResult(healthy=True, latency_ms=latency_ms)
            if response.status_code in (401, 403):
                return PluginHealthResult(
                    healthy=False,
                    latency_ms=latency_ms,
                    detail=f"Endpoint rejected the credentials (HTTP {response.status_code}).",
                )
            return PluginHealthResult(
                healthy=False,
                latency_ms=latency_ms,
                detail=f"Endpoint returned HTTP {response.status_code}.",
            )
        except httpx.TimeoutException:
            return PluginHealthResult(
                healthy=False,
                latency_ms=int(timeout_s * 1000),
                detail=f"Timed out after {timeout_s:.0f}s.",
            )
        except httpx.HTTPError as exc:
            return PluginHealthResult(
                healthy=False, latency_ms=None, detail=f"Unreachable: {exc}"
            )

    async def list_models(
        self, *, base_url: str | None, api_key: str | None, timeout_s: float = 10.0
    ) -> list[DiscoveredModel]:
        target = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        async with httpx.AsyncClient(timeout=timeout_s) as http:
            response = await http.get(f"{target}/v1/models", headers=_headers(api_key))
            response.raise_for_status()
            data = response.json().get("data", [])
        return [
            DiscoveredModel(
                model_id=m["id"], display_name=m.get("display_name", m["id"])
            )
            for m in data
            if "id" in m
        ]


PLUGIN = AnthropicPlugin
