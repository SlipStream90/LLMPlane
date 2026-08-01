"""`ollama` reference plugin (ARCHITECTURE.md §5.2).

`auth_type: "none"` — Ollama's local REST API has no credential concept, so
`health_check`/`list_models` ignore `api_key` when it is passed (the
interface still supplies it uniformly so callers don't need to special-case
auth type). Both operations hit the same `/api/tags` endpoint, the same path
`provider_health_service._PROBE[ProviderType.OLLAMA]` already used before
this plugin existed. `chat_completion`/`stream` are NOT overridden — they
inherit the `ProviderPlugin` defaults, which delegate to `GatewayClient`
(ADR-002).
"""

from __future__ import annotations

import time

import httpx

from app.plugins.base import DiscoveredModel, PluginHealthResult, ProviderPlugin


class OllamaPlugin(ProviderPlugin):
    async def health_check(
        self, *, base_url: str | None, api_key: str | None, timeout_s: float = 10.0
    ) -> PluginHealthResult:
        target = (base_url or "http://localhost:11434").rstrip("/")
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as http:
                response = await http.get(f"{target}/api/tags")
            latency_ms = int((time.perf_counter() - started) * 1000)
            if response.status_code == 200:
                return PluginHealthResult(healthy=True, latency_ms=latency_ms)
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
        target = (base_url or "http://localhost:11434").rstrip("/")
        async with httpx.AsyncClient(timeout=timeout_s) as http:
            response = await http.get(f"{target}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
        return [
            DiscoveredModel(model_id=m["name"], display_name=m["name"])
            for m in models
            if "name" in m
        ]


PLUGIN = OllamaPlugin
