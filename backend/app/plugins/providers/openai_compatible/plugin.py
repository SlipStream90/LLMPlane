"""`openai_compatible` reference plugin (ARCHITECTURE.md §5.1).

Covers any self-hosted/third-party endpoint that speaks the OpenAI `/v1`
schema (LM Studio, vLLM forks, internal gateways, Together, etc.).
`chat_completion`/`stream` are NOT overridden — they inherit the
`ProviderPlugin` defaults, which delegate to `GatewayClient` (ADR-002). This
plugin only owns the two read-only, provider-specific operations:
`health_check` and `list_models`.
"""

from __future__ import annotations

import time

import httpx

from app.plugins.base import DiscoveredModel, PluginHealthResult, ProviderPlugin


class OpenAICompatiblePlugin(ProviderPlugin):
    async def health_check(
        self, *, base_url: str | None, api_key: str | None, timeout_s: float = 10.0
    ) -> PluginHealthResult:
        if not base_url:
            return PluginHealthResult(
                healthy=False, latency_ms=None, detail="No base_url configured."
            )
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as http:
                response = await http.get(
                    f"{base_url.rstrip('/')}/models", headers=headers
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
        if not base_url:
            return []
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=timeout_s) as http:
            response = await http.get(
                f"{base_url.rstrip('/')}/v1/models", headers=headers
            )
            response.raise_for_status()
            data = response.json().get("data", [])
        return [
            DiscoveredModel(model_id=m["id"], display_name=m["id"])
            for m in data
            if "id" in m
        ]


PLUGIN = OpenAICompatiblePlugin
