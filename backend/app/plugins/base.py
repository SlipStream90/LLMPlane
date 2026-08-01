"""Provider plugin base interface (R1).

A plugin does two things `GatewayClient` and the static `ProviderType` model
cannot: (1) discover a provider's own model list and (2) define its own
health probe — both read-only, zero-cost operations against the provider's
native API. It never becomes a second path for actually running a completion;
see ADR-002. `chat_completion`/`embeddings`/`stream` exist on the interface so
callers have one uniform surface regardless of provider, but their bodies are
required to delegate to `GatewayClient`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

from app.services.gateway_client import CompletionResult, GatewayClient


@dataclass(frozen=True, slots=True)
class ProviderManifest:
    """Parsed, validated form of a plugin's manifest.json (§3)."""

    id: str  # e.g. "openai_compatible" — stored in Provider.plugin_id
    display_name: str
    auth_type: Literal["api_key", "none", "bearer_token"]
    default_base_url: str | None
    requires_base_url: bool
    capabilities: list[str]  # subset of {"chat", "embeddings", "streaming"}
    pricing_hint: dict[str, Any] | None = None  # optional default $/1M tokens


@dataclass(slots=True)
class DiscoveredModel:
    model_id: str
    display_name: str
    context_window: int | None = None
    capabilities: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PluginHealthResult:
    healthy: bool
    latency_ms: int | None
    detail: str | None = None


class ProviderPlugin(ABC):
    """One instance per registered plugin (not per `Provider` row).

    A `Provider` row references a plugin by `plugin_id`; the plugin instance
    is stateless with respect to any single provider connection — all
    connection-specific data (base_url, decrypted credentials) is passed into
    each method call by the caller (the API layer / health service), never
    cached on the plugin instance. This keeps the registry a process-wide
    singleton (§4) safe to share across requests and projects.
    """

    manifest: ProviderManifest

    def __init__(self, gateway: GatewayClient) -> None:
        self._gateway = gateway

    async def initialize(self) -> None:
        """Called once by the registry after discovery, before the plugin is
        exposed to callers. Default no-op; override for plugins that need to
        warm a cache or validate their manifest against a live schema."""
        return

    @abstractmethod
    async def health_check(
        self, *, base_url: str | None, api_key: str | None, timeout_s: float = 10.0
    ) -> PluginHealthResult:
        """Read-only reachability probe. Must not run a completion (cost)."""
        ...

    @abstractmethod
    async def list_models(
        self, *, base_url: str | None, api_key: str | None, timeout_s: float = 10.0
    ) -> list[DiscoveredModel]:
        """Read-only model catalog discovery against the provider's own API."""
        ...

    async def chat_completion(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """Default implementation: pure delegation to GatewayClient (ADR-002).

        Plugins normally do NOT override this — the default is the contract.
        A plugin overrides it only to adapt request shape (e.g. renaming a
        kwarg) before forwarding, never to call the provider directly.
        """
        return await self._gateway.chat_completion(
            model_id=model_id,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    async def embeddings(
        self, *, model_id: str, inputs: list[str], **kwargs: Any
    ) -> dict[str, Any]:
        """Delegates to GatewayClient. Raises NotImplementedError until
        GatewayClient grows an embeddings method — out of scope for this
        slice (no embeddings call site exists yet in gateway_client.py);
        declared on the interface now so plugins don't need a breaking
        signature change when it lands."""
        raise NotImplementedError(
            "embeddings() is declared on the interface for forward-"
            "compatibility; GatewayClient has no embeddings endpoint yet."
        )

    async def stream(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Delegates to GatewayClient. Same forward-compat note as
        embeddings(): GatewayClient has no streaming method yet; this slice
        does not add one. Declared so R1's interface is complete per the
        brief, implemented as NotImplementedError until a streaming
        GatewayClient method exists."""
        raise NotImplementedError(
            "stream() is declared on the interface for forward-"
            "compatibility; GatewayClient has no streaming endpoint yet."
        )
        yield ""  # pragma: no cover - keeps this an async generator

    async def shutdown(self) -> None:
        """Called once at app shutdown (lifespan). Default no-op; override
        for a plugin that opened a persistent resource in initialize()."""
        return
