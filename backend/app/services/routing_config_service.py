"""RoutingConfigService — translates `RoutingPolicy` rows into OpenRouter config.

With OpenRouter replacing LiteLLM, routing policies are stored in the database
and applied at the application level. This service validates models against the
registered catalog but no longer pushes config to an external gateway.

Phase 2+ could implement client-side routing (cost/latency-based) by querying
OpenRouter's model list and filtering based on the policy strategy.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import RoutingStrategy
from app.models.provider import Provider, ProviderModel
from app.models.routing import RoutingPolicy
from app.repositories.provider import ProviderModelRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfigPushResult:
    #: "applied" (policy saved) | "deferred" (saved, routing not yet active)
    status: str
    detail: str | None = None
    config_path: str | None = None

    @property
    def applied(self) -> bool:
        return self.status == "applied"


class RoutingConfigError(Exception):
    """Policy cannot be rendered into a valid config."""


class RoutingConfigService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def resolve_models(
        self, project_id: uuid.UUID, model_allowlist: list[str]
    ) -> list[ProviderModel]:
        """Map allow-listed `model_id`s onto registered catalog entries.

        Raises `RoutingConfigError` naming every unresolvable model.
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

    def render(
        self, policy: RoutingPolicy, models: list[ProviderModel]
    ) -> dict[str, Any]:
        """Build a routing config document. For display/storage only —
        OpenRouter handles actual routing."""
        model_list = []
        for model in models:
            model_list.append({
                "model_name": model.model_id,
                "provider": model.provider.provider_type.value,
                "model_info": {
                    "id": str(model.id),
                    "max_input_tokens": model.context_window,
                },
            })

        return {
            "policy_id": str(policy.id),
            "policy_name": policy.name,
            "strategy": policy.strategy.value,
            "model_list": model_list,
            "config": policy.config,
        }

    async def push(
        self, document: dict[str, Any], models: list[ProviderModel]
    ) -> ConfigPushResult:
        """Save the routing config. With OpenRouter, there's no gateway to push to."""
        logger.info(
            "Routing policy saved (OpenRouter handles routing): policy=%s",
            document.get("policy_name"),
        )
        return ConfigPushResult("applied")

    async def apply_policy(self, policy: RoutingPolicy) -> ConfigPushResult:
        """Validate and save a policy in one step."""
        models = await self.resolve_models(policy.project_id, policy.model_allowlist)
        document = self.render(policy, models)
        return await self.push(document, models)
