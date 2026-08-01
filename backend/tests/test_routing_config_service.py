"""RoutingConfigService rendering (T010).

The security-critical assertion here is that no plaintext credential ever
reaches the rendered `config.yaml`: on-disk config references credentials as
`os.environ/...` and the real values travel only over the HTTP push
(ARCHITECTURE.md 3.3, Article XII).
"""

from __future__ import annotations

import uuid

import pytest
import yaml

from app.models.enums import ProviderType, RoutingStrategy
from app.models.provider import Provider, ProviderModel
from app.models.routing import RoutingPolicy
from app.services.credential_service import CredentialService
from app.services.routing_config_service import (
    RoutingConfigService,
    _fallback_chain,
    _litellm_model_name,
    env_var_name,
)

SECRET = "sk-do-not-leak-me-9999"


def _provider(provider_type: ProviderType = ProviderType.OPENAI, **kwargs) -> Provider:
    provider = Provider(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        provider_type=provider_type,
        display_name=f"test-{provider_type.value}",
        is_active=True,
        **kwargs,
    )
    return provider


def _model(provider: Provider, model_id: str, **kwargs) -> ProviderModel:
    model = ProviderModel(
        id=uuid.uuid4(),
        provider_id=provider.id,
        model_id=model_id,
        display_name=model_id,
        context_window=128_000,
        capabilities=[],
        **kwargs,
    )
    model.provider = provider
    return model


def _policy(
    strategy: RoutingStrategy, config: dict, allowlist: list[str]
) -> RoutingPolicy:
    return RoutingPolicy(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="test-policy",
        strategy=strategy,
        config=config,
        model_allowlist=allowlist,
        is_active=False,
    )


@pytest.fixture
def service() -> RoutingConfigService:
    return RoutingConfigService(session=None)  # type: ignore[arg-type]


def test_rendered_config_never_contains_a_plaintext_key(
    service, tmp_path, monkeypatch
) -> None:
    credentials = CredentialService()
    provider = _provider(credentials_encrypted=credentials.encrypt({"api_key": SECRET}))
    models = [_model(provider, "gpt-4.1")]
    policy = _policy(RoutingStrategy.CHEAPEST, {}, ["gpt-4.1"])

    document = service.render(policy, models)
    params = document["model_list"][0]["litellm_params"]
    assert params["api_key"] == f"os.environ/{env_var_name(provider)}"

    monkeypatch.setattr(
        service.settings, "litellm_config_path", str(tmp_path / "config.yaml")
    )
    path = service.write_config_file(document)
    with open(path, encoding="utf-8") as f:
        written = f.read()

    assert SECRET not in written
    assert "os.environ/" in written
    # And it must still be valid YAML the gateway can load.
    assert yaml.safe_load(written)["model_list"][0]["model_name"] == "gpt-4.1"


def test_live_push_document_carries_the_real_credential(service) -> None:
    """The HTTP push is the one path that may carry secrets — otherwise a
    provider added at runtime could never work without restarting the gateway."""
    credentials = CredentialService()
    provider = _provider(credentials_encrypted=credentials.encrypt({"api_key": SECRET}))
    models = [_model(provider, "gpt-4.1")]
    document = service.render(
        _policy(RoutingStrategy.CHEAPEST, {}, ["gpt-4.1"]), models
    )

    live = service._with_live_credentials(document, models)

    assert live["model_list"][0]["litellm_params"]["api_key"] == SECRET
    # The original document must not be mutated by building the live copy.
    assert document["model_list"][0]["litellm_params"]["api_key"].startswith(
        "os.environ/"
    )


def test_local_providers_get_an_api_base_and_no_key(service) -> None:
    provider = _provider(
        ProviderType.OLLAMA, base_url="http://host.docker.internal:11500"
    )
    models = [_model(provider, "llama3.1:8b")]

    params = service.render(
        _policy(RoutingStrategy.ROUND_ROBIN, {}, ["llama3.1:8b"]), models
    )["model_list"][0]["litellm_params"]

    assert params["api_base"] == "http://host.docker.internal:11500"
    assert "api_key" not in params
    assert params["model"] == "ollama/llama3.1:8b"


def test_weights_are_applied_only_to_listed_models(service) -> None:
    provider = _provider()
    models = [_model(provider, "gpt-4.1"), _model(provider, "gpt-4o-mini")]
    policy = _policy(
        RoutingStrategy.WEIGHTED,
        {"weights": {"gpt-4.1": 3}},
        ["gpt-4.1", "gpt-4o-mini"],
    )

    entries = {
        e["model_name"]: e["litellm_params"]
        for e in service.render(policy, models)["model_list"]
    }

    assert entries["gpt-4.1"]["weight"] == 3
    assert "weight" not in entries["gpt-4o-mini"]


def test_pricing_is_converted_to_per_token(service) -> None:
    from decimal import Decimal

    provider = _provider()
    models = [
        _model(
            provider,
            "gpt-4.1",
            input_price_per_1m=Decimal("2.50"),
            output_price_per_1m=Decimal("10.00"),
        )
    ]

    params = service.render(_policy(RoutingStrategy.CHEAPEST, {}, ["gpt-4.1"]), models)[
        "model_list"
    ][0]["litellm_params"]

    assert params["input_cost_per_token"] == pytest.approx(2.5e-6)
    assert params["output_cost_per_token"] == pytest.approx(1e-5)


def test_fallback_chain_shape() -> None:
    assert _fallback_chain(["a", "b", "c"]) == [{"a": ["b", "c"]}, {"b": ["c"]}]
    assert _fallback_chain(["only"]) == []
    assert _fallback_chain([]) == []


def test_already_qualified_model_names_are_not_double_prefixed() -> None:
    provider = _provider(ProviderType.OPENAI)
    model = _model(provider, "openai/gpt-4.1")
    assert _litellm_model_name(model, provider) == "openai/gpt-4.1"


def test_cache_stays_off_unless_the_policy_opts_in(service) -> None:
    """Alpha ships an exact-match cache only, opt-in per policy
    (ARCHITECTURE.md 4.4). It must not be on by default."""
    provider = _provider()
    models = [_model(provider, "gpt-4.1")]

    off = service.render(_policy(RoutingStrategy.CHEAPEST, {}, ["gpt-4.1"]), models)
    on = service.render(
        _policy(RoutingStrategy.CHEAPEST, {"enable_cache": True}, ["gpt-4.1"]), models
    )

    assert off["litellm_settings"]["cache"] is False
    assert "cache_params" not in off["litellm_settings"]
    assert on["litellm_settings"]["cache_params"]["type"] == "redis"
