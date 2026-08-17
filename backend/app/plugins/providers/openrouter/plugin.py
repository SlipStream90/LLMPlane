"""OpenRouter plugin — filters for free models only.

OpenRouter marks free models with `:free` suffix in the model ID.
This plugin only returns models that are free to use.
"""

from __future__ import annotations

import time

import httpx

from app.plugins.base import DiscoveredModel, PluginHealthResult, ProviderPlugin


class OpenRouterPlugin(ProviderPlugin):
    async def health_check(
        self, *, base_url: str | None, api_key: str | None, timeout_s: float = 10.0
    ) -> PluginHealthResult:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as http:
                response = await http.get(
                    "https://openrouter.ai/api/v1/models", headers=headers
                )
            latency_ms = int((time.perf_counter() - started) * 1000)
            if response.status_code == 200:
                return PluginHealthResult(healthy=True, latency_ms=latency_ms)
            if response.status_code in (401, 403):
                return PluginHealthResult(
                    healthy=False,
                    latency_ms=latency_ms,
                    detail=f"OpenRouter rejected the API key (HTTP {response.status_code}).",
                )
            return PluginHealthResult(
                healthy=False,
                latency_ms=latency_ms,
                detail=f"OpenRouter returned HTTP {response.status_code}.",
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
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=timeout_s) as http:
            response = await http.get(
                "https://openrouter.ai/api/v1/models", headers=headers
            )
            response.raise_for_status()
            data = response.json().get("data", [])

        free_models = []
        for m in data:
            model_id = m.get("id", "")
            if not model_id:
                continue

            # Only include models marked as free (suffix :free)
            if not model_id.endswith(":free"):
                continue

            # Extract pricing info
            pricing = m.get("pricing", {})
            prompt_price = float(pricing.get("prompt", "1") or "1")
            completion_price = float(pricing.get("completion", "1") or "1")

            # Double-check: skip if pricing is non-zero
            if prompt_price > 0 or completion_price > 0:
                continue

            context_length = m.get("context_length", 8192)
            free_models.append(
                DiscoveredModel(
                    model_id=model_id,
                    display_name=model_id.replace(":free", "").replace("/", " / "),
                    context_window=context_length,
                )
            )

        return free_models


PLUGIN = OpenRouterPlugin
