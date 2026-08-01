"""Routing policy schemas, including per-strategy config validation.

Strategy config is a JSONB blob in the database, but it is *not* unvalidated:
each strategy declares the keys it needs, and a policy that cannot be rendered
into a working LiteLLM config is rejected at write time rather than failing
later at activation (or worse, silently routing nowhere).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.enums import RoutingStrategy
from app.schemas.common import ORMModel

#: Required config keys per strategy.
REQUIRED_CONFIG_KEYS: dict[RoutingStrategy, tuple[str, ...]] = {
    RoutingStrategy.CHEAPEST: (),
    RoutingStrategy.FASTEST: (),
    RoutingStrategy.ROUND_ROBIN: (),
    RoutingStrategy.FALLBACK: ("fallback_order",),
    RoutingStrategy.WEIGHTED: ("weights",),
    RoutingStrategy.COST_THRESHOLD: ("max_cost_per_1k_tokens_usd",),
    RoutingStrategy.LATENCY_THRESHOLD: ("max_latency_ms",),
}


class RoutingPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    strategy: RoutingStrategy
    config: dict[str, Any] = Field(default_factory=dict)
    model_allowlist: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_config(self) -> "RoutingPolicyCreate":
        missing = [
            key
            for key in REQUIRED_CONFIG_KEYS[self.strategy]
            if key not in self.config
        ]
        if missing:
            raise ValueError(
                f"strategy '{self.strategy}' requires config key(s): {', '.join(missing)}"
            )

        if self.strategy is RoutingStrategy.WEIGHTED:
            weights = self.config.get("weights")
            if not isinstance(weights, dict) or not weights:
                raise ValueError("config.weights must be a non-empty {model_id: weight} map")
            unknown = set(weights) - set(self.model_allowlist)
            if unknown:
                raise ValueError(
                    f"config.weights references models outside model_allowlist: "
                    f"{', '.join(sorted(unknown))}"
                )
            if any(not isinstance(w, (int, float)) or w <= 0 for w in weights.values()):
                raise ValueError("config.weights values must be positive numbers")

        if self.strategy is RoutingStrategy.FALLBACK:
            order = self.config.get("fallback_order")
            if not isinstance(order, list) or len(order) < 2:
                raise ValueError(
                    "config.fallback_order must list at least two model ids, in order"
                )
            unknown = set(order) - set(self.model_allowlist)
            if unknown:
                raise ValueError(
                    f"config.fallback_order references models outside model_allowlist: "
                    f"{', '.join(sorted(unknown))}"
                )
        return self


class RoutingPolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: dict[str, Any] | None = None
    model_allowlist: list[str] | None = Field(default=None, min_length=1)


class RoutingPolicyOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    strategy: RoutingStrategy
    config: dict[str, Any]
    model_allowlist: list[str]
    is_active: bool
    created_at: datetime


class RoutingPolicyActivated(RoutingPolicyOut):
    #: "applied" — the gateway accepted a hot config reload.
    #: "deferred" — the config file was written but the gateway did not accept
    #: the reload; it takes effect on the gateway's next restart. Reported
    #: honestly rather than presented as success (Article V).
    gateway_config_status: str
    gateway_detail: str | None = None
