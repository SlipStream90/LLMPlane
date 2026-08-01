"""RoutingConfigService — translates `RoutingPolicy` rows into the gateway's
LiteLLM router config and pushes it (T010, ARCHITECTURE.md 3.3).

`backend` authors policy; the gateway executes it. Two artifacts are produced
from one policy:

1. **A `config.yaml` on the volume shared with the gateway container.** This is
   the durable form, read by LiteLLM Proxy on (re)start. Credentials appear
   here only as `os.environ/NAME` *references* — never as plaintext
   (ARCHITECTURE.md 3.3, Article XII).
2. **An HTTP push to the running gateway** so a policy change takes effect
   without a restart.

Endpoint verification (the T010 note asked for this explicitly): LiteLLM's
proxy config documentation at https://docs.litellm.ai/docs/proxy/configs —
checked 2026-08-01 against pinned stable 1.94.1 — documents `POST
/config/update`, not `/config/reload`. The path is configurable
(`GATEWAY_CONFIG_UPDATE_PATH`) so a tag change does not require a code change.
If the push fails for any reason, the on-disk config is still written and the
result is reported as **deferred**, meaning "will apply on gateway restart" —
never as success (Article V).
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import ProviderType, RoutingStrategy
from app.models.provider import Provider, ProviderModel
from app.models.routing import RoutingPolicy
from app.repositories.provider import ProviderModelRepository
from app.services.credential_service import CredentialService

logger = logging.getLogger(__name__)

#: RoutingPolicy.strategy -> LiteLLM `router_settings.routing_strategy`.
#: LiteLLM has no native "cheapest"/"fastest" name; both map onto its
#: cost/latency-based routing strategies. `fallback`, `cost_threshold` and
#: `latency_threshold` are expressed through router settings + fallbacks rather
#: than a strategy name, so they fall back to simple shuffle for selection.
LITELLM_STRATEGY: dict[RoutingStrategy, str] = {
    RoutingStrategy.CHEAPEST: "cost-based-routing",
    RoutingStrategy.FASTEST: "latency-based-routing",
    RoutingStrategy.LATENCY_THRESHOLD: "latency-based-routing",
    RoutingStrategy.COST_THRESHOLD: "cost-based-routing",
    RoutingStrategy.ROUND_ROBIN: "simple-shuffle",
    RoutingStrategy.WEIGHTED: "simple-shuffle",
    RoutingStrategy.FALLBACK: "simple-shuffle",
}

#: Env var name the gateway is expected to resolve for a provider's key.
def env_var_name(provider: Provider) -> str:
    return f"LLMPLANE_PROVIDER_{provider.id.hex[:12].upper()}_API_KEY"


@dataclass(frozen=True)
class ConfigPushResult:
    #: "applied" (gateway hot-reloaded) | "deferred" (written, needs restart)
    status: str
    detail: str | None = None
    config_path: str | None = None

    @property
    def applied(self) -> bool:
        return self.status == "applied"


class RoutingConfigError(Exception):
    """Policy cannot be rendered into a valid gateway config."""


class RoutingConfigService:
    def __init__(
        self,
        session: AsyncSession,
        credentials: CredentialService | None = None,
    ) -> None:
        self.session = session
        self.settings = get_settings()
        self.credentials = credentials or CredentialService()

    # -- validation --------------------------------------------------------
    async def resolve_models(
        self, project_id: uuid.UUID, model_allowlist: list[str]
    ) -> list[ProviderModel]:
        """Map allow-listed `model_id`s onto registered catalog entries.

        Raises `RoutingConfigError` naming every unresolvable model — this is
        what produces the 409 on activate (api-contracts.md 3) instead of
        pushing a config that routes to nothing.
        """
        repo = ProviderModelRepository(self.session)
        catalog = {m.model_id: m for m in await repo.list_for_project(project_id)}
        missing = [m for m in model_allowlist if m not in catalog]
        if missing:
            raise RoutingConfigError(
                "model_allowlist references models that are not registered under "
                f"any provider in this project: {', '.join(sorted(missing))}"
            )
        resolved = [catalog[m] for m in model_allowlist]
        inactive = [m.model_id for m in resolved if not m.provider.is_active]
        if inactive:
            raise RoutingConfigError(
                "model_allowlist references models on inactive providers: "
                f"{', '.join(sorted(inactive))}"
            )
        return resolved

    # -- rendering ---------------------------------------------------------
    def render(
        self, policy: RoutingPolicy, models: list[ProviderModel]
    ) -> dict[str, Any]:
        """Build the LiteLLM config document. No secrets in the result."""
        weights: dict[str, float] = policy.config.get("weights", {}) or {}

        model_list: list[dict[str, Any]] = []
        for model in models:
            provider = model.provider
            params: dict[str, Any] = {"model": _litellm_model_name(model, provider)}

            if provider.base_url:
                params["api_base"] = provider.base_url
            if provider.provider_type not in (ProviderType.OLLAMA, ProviderType.VLLM):
                # Reference, not value. The running gateway gets the real key
                # via the HTTP push below; the file on disk never holds one.
                params["api_key"] = f"os.environ/{env_var_name(provider)}"
            if model.input_price_per_1m is not None:
                params["input_cost_per_token"] = float(model.input_price_per_1m) / 1_000_000
            if model.output_price_per_1m is not None:
                params["output_cost_per_token"] = (
                    float(model.output_price_per_1m) / 1_000_000
                )
            if policy.strategy is RoutingStrategy.WEIGHTED and model.model_id in weights:
                params["weight"] = weights[model.model_id]
            if policy.strategy is RoutingStrategy.LATENCY_THRESHOLD:
                timeout_ms = policy.config.get("max_latency_ms")
                if timeout_ms:
                    params["timeout"] = float(timeout_ms) / 1000.0

            model_list.append(
                {
                    "model_name": model.model_id,
                    "litellm_params": params,
                    "model_info": {
                        "id": str(model.id),
                        "max_input_tokens": model.context_window,
                        "llmplane_provider_id": str(provider.id),
                    },
                }
            )

        router_settings: dict[str, Any] = {
            "routing_strategy": LITELLM_STRATEGY[policy.strategy],
            "num_retries": int(policy.config.get("num_retries", 2)),
            "allowed_fails": int(policy.config.get("allowed_fails", 3)),
        }
        if policy.strategy is RoutingStrategy.FALLBACK:
            router_settings["fallbacks"] = _fallback_chain(
                policy.config.get("fallback_order", [])
            )
        if policy.strategy is RoutingStrategy.COST_THRESHOLD:
            # Recorded for operator visibility; enforcement of a hard per-call
            # cost ceiling is not a LiteLLM router feature, so the threshold
            # drives model ordering via cost-based routing rather than a block.
            router_settings["llmplane_max_cost_per_1k_tokens_usd"] = policy.config[
                "max_cost_per_1k_tokens_usd"
            ]

        document: dict[str, Any] = {
            "model_list": model_list,
            "router_settings": router_settings,
            "litellm_settings": {
                "drop_params": True,
                "success_callback": ["otel"],
                "failure_callback": ["otel"],
                # Exact-match response cache only. The semantic/vector layer is
                # explicitly Phase 3+ (ARCHITECTURE.md 4.4) and is not enabled
                # here.
                "cache": bool(policy.config.get("enable_cache", False)),
            },
            "general_settings": {
                "llmplane_policy_id": str(policy.id),
                "llmplane_policy_name": policy.name,
            },
        }
        if document["litellm_settings"]["cache"]:
            document["litellm_settings"]["cache_params"] = {
                "type": "redis",
                "ttl": int(policy.config.get("cache_ttl_s", 300)),
            }
        return document

    def write_config_file(self, document: dict[str, Any]) -> str:
        """Atomically write the rendered config onto the shared volume.

        Atomic because the gateway may read the file at any moment — a
        half-written config is a broken gateway, and rename(2) within a
        filesystem is the cheap way to never expose one.
        """
        path = self.settings.litellm_config_path
        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(document, handle, sort_keys=False, default_flow_style=False)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        return path

    # -- push --------------------------------------------------------------
    async def push(
        self, document: dict[str, Any], models: list[ProviderModel]
    ) -> ConfigPushResult:
        """Write the config and try to hot-reload the gateway."""
        path = self.write_config_file(document)

        # The pushed copy carries real credentials so a runtime-added provider
        # works without restarting the gateway to pick up a new env var. This
        # travels over the internal Compose network to the gateway process and
        # is never written to disk (infrastructure.md 2).
        live_document = self._with_live_credentials(document, models)

        try:
            async with httpx.AsyncClient(timeout=20.0) as http:
                response = await http.post(
                    self.settings.gateway_config_update_url,
                    json=live_document,
                    headers={
                        "Authorization": f"Bearer {self.settings.litellm_master_key}",
                        "Content-Type": "application/json",
                    },
                )
            if response.status_code < 400:
                return ConfigPushResult("applied", config_path=path)

            detail = (
                f"gateway rejected the config update with HTTP "
                f"{response.status_code}; the config file was written and will "
                f"apply on the gateway's next restart"
            )
            logger.warning("%s (path=%s)", detail, path)
            return ConfigPushResult("deferred", detail, path)
        except httpx.HTTPError as exc:
            detail = (
                f"gateway config endpoint unreachable ({exc}); the config file "
                f"was written and will apply on the gateway's next restart"
            )
            logger.warning("%s (path=%s)", detail, path)
            return ConfigPushResult("deferred", detail, path)

    def _with_live_credentials(
        self, document: dict[str, Any], models: list[ProviderModel]
    ) -> dict[str, Any]:
        by_model_name: dict[str, ProviderModel] = {m.model_id: m for m in models}
        live: dict[str, Any] = {
            **document,
            "model_list": [dict(entry) for entry in document["model_list"]],
        }
        for entry in live["model_list"]:
            model = by_model_name.get(entry["model_name"])
            if model is None:
                continue
            params = dict(entry["litellm_params"])
            api_key = self.credentials.api_key_of(model.provider.credentials_encrypted)
            if api_key:
                params["api_key"] = api_key
            elif "api_key" in params:
                # Leave the os.environ reference in place rather than sending a
                # null and breaking an otherwise-working provider.
                pass
            entry["litellm_params"] = params
        return live

    # -- orchestration -----------------------------------------------------
    async def apply_policy(self, policy: RoutingPolicy) -> ConfigPushResult:
        """Validate, render, write and push a policy in one step."""
        models = await self.resolve_models(policy.project_id, policy.model_allowlist)
        document = self.render(policy, models)
        return await self.push(document, models)


def _litellm_model_name(model: ProviderModel, provider: Provider) -> str:
    """LiteLLM's provider-qualified model name (`anthropic/claude-opus-5`).

    Already-qualified ids are passed through unchanged so a user who typed the
    full LiteLLM name does not end up with `openai/openai/gpt-4.1`.
    """
    if "/" in model.model_id:
        return model.model_id
    prefix = {
        ProviderType.OPENAI: "openai",
        ProviderType.ANTHROPIC: "anthropic",
        ProviderType.GEMINI: "gemini",
        ProviderType.GROQ: "groq",
        ProviderType.MISTRAL: "mistral",
        ProviderType.COHERE: "cohere",
        ProviderType.OPENROUTER: "openrouter",
        ProviderType.AZURE_OPENAI: "azure",
        ProviderType.AWS_BEDROCK: "bedrock",
        ProviderType.OLLAMA: "ollama",
        ProviderType.VLLM: "hosted_vllm",
    }[provider.provider_type]
    return f"{prefix}/{model.model_id}"


def _fallback_chain(order: list[str]) -> list[dict[str, list[str]]]:
    """LiteLLM fallbacks format: `[{primary: [next, next-next]}]`."""
    return [{order[i]: order[i + 1 :]} for i in range(len(order) - 1)]
