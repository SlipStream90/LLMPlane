"""Provider health checks (T016).

`Provider.health_status` is written by a check, never computed on read
(data-models.md 2) — a dashboard rendering 12 provider cards must not trigger
12 outbound provider calls.

The check is a cheap, read-only model-list call against the provider's own API
(or the local endpoint for Ollama/vLLM). It deliberately does not run a
completion: that would cost money on every health poll.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HealthStatus, ProviderType
from app.models.provider import Provider
from app.plugins.registry import get_plugin_registry
from app.services.credential_service import CredentialService

logger = logging.getLogger(__name__)

#: Latency above which a reachable provider is reported degraded rather than
#: healthy.
DEGRADED_LATENCY_MS = 3000

#: Read-only probe endpoint per provider type, relative to its base URL.
_PROBE: dict[ProviderType, tuple[str, str]] = {
    ProviderType.OPENAI: ("https://api.openai.com/v1", "/models"),
    ProviderType.ANTHROPIC: ("https://api.anthropic.com/v1", "/models"),
    ProviderType.GEMINI: (
        "https://generativelanguage.googleapis.com/v1beta",
        "/models",
    ),
    ProviderType.GROQ: ("https://api.groq.com/openai/v1", "/models"),
    ProviderType.MISTRAL: ("https://api.mistral.ai/v1", "/models"),
    ProviderType.COHERE: ("https://api.cohere.com/v1", "/models"),
    ProviderType.OPENROUTER: ("https://openrouter.ai/api/v1", "/models"),
    ProviderType.OLLAMA: ("http://localhost:11434", "/api/tags"),
    ProviderType.VLLM: ("http://localhost:8000", "/v1/models"),
}


@dataclass(frozen=True)
class HealthCheckResult:
    status: HealthStatus
    latency_ms: int | None
    checked_at: datetime
    detail: str | None = None


class ProviderHealthService:
    def __init__(
        self, session: AsyncSession, credentials: CredentialService | None = None
    ) -> None:
        self.session = session
        self.credentials = credentials or CredentialService()

    async def check(
        self, provider: Provider, *, timeout_s: float = 10.0
    ) -> HealthCheckResult:
        """Probe one provider and persist the outcome."""
        result = await self._probe(provider, timeout_s)
        provider.health_status = result.status
        provider.last_health_check_at = result.checked_at
        provider.last_latency_ms = result.latency_ms
        await self.session.flush()
        logger.info(
            "provider health check",
            extra={
                "provider": provider.display_name,
                "provider_type": str(provider.provider_type),
                "status": str(result.status),
            },
        )
        return result

    async def check_all(
        self, providers: list[Provider]
    ) -> dict[str, HealthCheckResult]:
        out: dict[str, HealthCheckResult] = {}
        for provider in providers:
            out[str(provider.id)] = await self.check(provider)
        return out

    async def _probe(self, provider: Provider, timeout_s: float) -> HealthCheckResult:
        now = datetime.now(timezone.utc)

        # Azure and Bedrock need per-deployment/region routing that a generic
        # probe cannot construct. Reporting `unknown` with a reason is honest;
        # reporting `healthy` because we did not check would not be.
        if provider.provider_type in (
            ProviderType.AZURE_OPENAI,
            ProviderType.AWS_BEDROCK,
        ):
            return HealthCheckResult(
                HealthStatus.UNKNOWN,
                None,
                now,
                f"No generic health probe for '{provider.provider_type}' — "
                "verify through a gateway completion instead.",
            )

        if provider.plugin_id:
            return await self._probe_via_plugin(provider, now, timeout_s)

        probe_entry = _PROBE.get(provider.provider_type)
        if probe_entry is None:
            # No plugin backing this provider and no static probe entry
            # either (e.g. a first-party type added without a probe, or a
            # CUSTOM provider whose plugin_id somehow went missing). Honest
            # "unknown" beats a false "healthy", matching the
            # Azure/Bedrock pattern above.
            return HealthCheckResult(
                HealthStatus.UNKNOWN,
                None,
                now,
                f"No generic health probe for '{provider.provider_type}'.",
            )

        default_base, path = probe_entry
        base_url = (provider.base_url or default_base).rstrip("/")
        headers = self._auth_headers(provider)

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as http:
                response = await http.get(f"{base_url}{path}", headers=headers)
            latency_ms = int((time.perf_counter() - started) * 1000)

            if response.status_code in (401, 403):
                return HealthCheckResult(
                    HealthStatus.DOWN,
                    latency_ms,
                    now,
                    "Provider rejected the stored credentials (HTTP "
                    f"{response.status_code}).",
                )
            if response.status_code >= 500:
                return HealthCheckResult(
                    HealthStatus.DOWN,
                    latency_ms,
                    now,
                    f"Provider returned HTTP {response.status_code}.",
                )
            if response.status_code >= 400:
                return HealthCheckResult(
                    HealthStatus.DEGRADED,
                    latency_ms,
                    now,
                    f"Probe endpoint returned HTTP {response.status_code}.",
                )
            if latency_ms > DEGRADED_LATENCY_MS:
                return HealthCheckResult(
                    HealthStatus.DEGRADED,
                    latency_ms,
                    now,
                    f"Reachable but slow ({latency_ms} ms).",
                )
            return HealthCheckResult(HealthStatus.HEALTHY, latency_ms, now)
        except httpx.TimeoutException:
            return HealthCheckResult(
                HealthStatus.DOWN,
                int(timeout_s * 1000),
                now,
                f"Timed out after {timeout_s:.0f}s.",
            )
        except httpx.HTTPError as exc:
            return HealthCheckResult(
                HealthStatus.DOWN, None, now, f"Unreachable: {exc}"
            )

    async def _probe_via_plugin(
        self, provider: Provider, now: datetime, timeout_s: float
    ) -> HealthCheckResult:
        """Delegate to the plugin named by `provider.plugin_id` (ADR-003
        consequence #1). Falls back to `UNKNOWN` — never `KeyError` — if the
        plugin isn't registered, matching the existing Azure/Bedrock honesty
        pattern rather than raising out of a health poll."""
        plugin = get_plugin_registry().get(provider.plugin_id)  # type: ignore[arg-type]
        if plugin is None:
            return HealthCheckResult(
                HealthStatus.UNKNOWN,
                None,
                now,
                f"Plugin '{provider.plugin_id}' is not registered — cannot probe.",
            )
        api_key = self.credentials.api_key_of(provider.credentials_encrypted)
        result = await plugin.health_check(
            base_url=provider.base_url, api_key=api_key, timeout_s=timeout_s
        )
        if not result.healthy:
            return HealthCheckResult(
                HealthStatus.DOWN, result.latency_ms, now, result.detail
            )
        if result.latency_ms is not None and result.latency_ms > DEGRADED_LATENCY_MS:
            return HealthCheckResult(
                HealthStatus.DEGRADED,
                result.latency_ms,
                now,
                result.detail or f"Reachable but slow ({result.latency_ms} ms).",
            )
        return HealthCheckResult(
            HealthStatus.HEALTHY, result.latency_ms, now, result.detail
        )

    def _auth_headers(self, provider: Provider) -> dict[str, str]:
        api_key = self.credentials.api_key_of(provider.credentials_encrypted)
        if not api_key:
            return {}
        if provider.provider_type is ProviderType.ANTHROPIC:
            return {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        if provider.provider_type is ProviderType.GEMINI:
            return {"x-goog-api-key": api_key}
        return {"Authorization": f"Bearer {api_key}"}
