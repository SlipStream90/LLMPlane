"""RoutingConfigService model resolution and rendering (T010).

Since commit 40a457f replaced LiteLLM with OpenRouter there is no gateway
config file and no credential injection: the service validates a policy's
allowlist against the project catalog and renders a document that is only ever
displayed or stored. The security-critical assertion carries over unchanged —
no plaintext provider credential may reach the rendered document
(ARCHITECTURE.md 3.3, Article XII).
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest

from app.models.enums import ProviderType, RoutingStrategy
from app.models.provider import Provider, ProviderModel
from app.models.routing import RoutingPolicy
from app.services.credential_service import CredentialService
from app.services.routing_config_service import (
    ConfigPushResult,
    RoutingConfigError,
    RoutingConfigService,
)

SECRET = "sk-do-not-leak-me-9999"


def _provider(
    provider_type: ProviderType = ProviderType.OPENAI, **kwargs
) -> Provider:
    kwargs.setdefault("is_active", True)
    return Provider(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        provider_type=provider_type,
        display_name=f"test-{provider_type.value}",
        **kwargs,
    )


def _model(provider: Provider, model_id: str, **kwargs) -> ProviderModel:
    kwargs.setdefault("context_window", 128_000)
    model = ProviderModel(
        id=uuid.uuid4(),
        provider_id=provider.id,
        model_id=model_id,
        display_name=model_id,
        capabilities=[],
        **kwargs,
    )
    model.provider = provider
    return model


def _policy(
    strategy: RoutingStrategy,
    config: dict,
    allowlist: list[str],
    project_id: uuid.UUID | None = None,
) -> RoutingPolicy:
    return RoutingPolicy(
        id=uuid.uuid4(),
        project_id=project_id or uuid.uuid4(),
        name="test-policy",
        strategy=strategy,
        config=config,
        model_allowlist=allowlist,
        is_active=False,
    )


@pytest.fixture
def service() -> RoutingConfigService:
    return RoutingConfigService(session=None)  # type: ignore[arg-type]


@pytest.fixture
def stub_catalog(monkeypatch):
    """Replace the repository the service constructs internally.

    `resolve_models` is the only DB-touching path; stubbing the repository
    keeps these tests in the unit tier (see tests/conftest.py).
    """

    def install(models: list[ProviderModel]) -> None:
        class _StubRepo:
            def __init__(self, session) -> None:
                self.session = session

            async def list_for_project(
                self, project_id: uuid.UUID
            ) -> list[ProviderModel]:
                return list(models)

        monkeypatch.setattr(
            "app.services.routing_config_service.ProviderModelRepository", _StubRepo
        )

    return install


# -- rendering -------------------------------------------------------------


def test_rendered_config_never_contains_a_plaintext_key(service) -> None:
    """The rendered document is display/storage-only and may be persisted or
    returned to a client, so it must never carry credential material."""
    credentials = CredentialService()
    provider = _provider(
        credentials_encrypted=credentials.encrypt({"api_key": SECRET})
    )
    models = [_model(provider, "gpt-4.1")]
    policy = _policy(RoutingStrategy.CHEAPEST, {}, ["gpt-4.1"])

    document = service.render(policy, models)
    serialized = json.dumps(document, default=str)

    assert SECRET not in serialized
    assert "api_key" not in serialized
    assert "credentials" not in serialized
    # The document is still complete enough to identify the deployment.
    assert document["model_list"][0]["model_name"] == "gpt-4.1"


def test_render_describes_the_policy_and_its_models(service) -> None:
    provider = _provider()
    models = [_model(provider, "gpt-4.1"), _model(provider, "gpt-4o-mini")]
    policy = _policy(
        RoutingStrategy.WEIGHTED, {"weights": {"gpt-4.1": 3}}, ["gpt-4.1", "gpt-4o-mini"]
    )

    document = service.render(policy, models)

    assert document["policy_id"] == str(policy.id)
    assert document["policy_name"] == "test-policy"
    assert document["strategy"] == "weighted"
    assert document["config"] == {"weights": {"gpt-4.1": 3}}
    assert [e["model_name"] for e in document["model_list"]] == [
        "gpt-4.1",
        "gpt-4o-mini",
    ]


def test_render_carries_provider_type_and_model_info(service) -> None:
    provider = _provider(ProviderType.OLLAMA, base_url="http://localhost:11500")
    model = _model(provider, "llama3.1:8b", context_window=8192)

    entry = service.render(
        _policy(RoutingStrategy.ROUND_ROBIN, {}, ["llama3.1:8b"]), [model]
    )["model_list"][0]

    assert entry["provider"] == "ollama"
    assert entry["model_info"] == {
        "id": str(model.id),
        "max_input_tokens": 8192,
    }


def test_render_of_an_empty_allowlist_yields_an_empty_model_list(service) -> None:
    document = service.render(_policy(RoutingStrategy.CHEAPEST, {}, []), [])

    assert document["model_list"] == []
    assert document["strategy"] == "cheapest"


def test_pricing_metadata_is_not_leaked_into_the_document(service) -> None:
    """Pricing lives in the catalog; OpenRouter does the cost accounting, so
    the rendered document deliberately carries no price fields."""
    provider = _provider()
    model = _model(
        provider,
        "gpt-4.1",
        input_price_per_1m=Decimal("2.50"),
        output_price_per_1m=Decimal("10.00"),
    )

    entry = service.render(
        _policy(RoutingStrategy.CHEAPEST, {}, ["gpt-4.1"]), [model]
    )["model_list"][0]

    assert "input_cost_per_token" not in entry
    assert "input_price_per_1m" not in entry["model_info"]


# -- model resolution ------------------------------------------------------


async def test_resolve_models_returns_catalog_rows_in_allowlist_order(
    service, stub_catalog
) -> None:
    provider = _provider()
    catalog = [
        _model(provider, "gpt-4.1"),
        _model(provider, "gpt-4o-mini"),
        _model(provider, "unlisted"),
    ]
    stub_catalog(catalog)

    resolved = await service.resolve_models(
        uuid.uuid4(), ["gpt-4o-mini", "gpt-4.1"]
    )

    assert [m.model_id for m in resolved] == ["gpt-4o-mini", "gpt-4.1"]


async def test_resolve_models_rejects_unregistered_models(
    service, stub_catalog
) -> None:
    provider = _provider()
    stub_catalog([_model(provider, "gpt-4.1")])

    with pytest.raises(RoutingConfigError) as exc:
        await service.resolve_models(uuid.uuid4(), ["gpt-4.1", "ghost", "phantom"])

    message = str(exc.value)
    assert "ghost" in message and "phantom" in message
    assert "gpt-4.1" not in message


async def test_resolve_models_rejects_models_on_inactive_providers(
    service, stub_catalog
) -> None:
    inactive = _provider(is_active=False)
    stub_catalog([_model(inactive, "gpt-4.1")])

    with pytest.raises(RoutingConfigError, match="inactive providers"):
        await service.resolve_models(uuid.uuid4(), ["gpt-4.1"])


async def test_resolve_models_accepts_an_empty_allowlist(
    service, stub_catalog
) -> None:
    stub_catalog([])

    assert await service.resolve_models(uuid.uuid4(), []) == []


# -- push / apply ----------------------------------------------------------


async def test_push_reports_applied_without_a_gateway(service) -> None:
    """OpenRouter needs no config push; the policy is simply saved."""
    provider = _provider()
    models = [_model(provider, "gpt-4.1")]
    document = service.render(
        _policy(RoutingStrategy.CHEAPEST, {}, ["gpt-4.1"]), models
    )

    result = await service.push(document, models)

    assert isinstance(result, ConfigPushResult)
    assert result.status == "applied"
    assert result.applied is True
    assert result.config_path is None


def test_deferred_result_is_not_applied() -> None:
    result = ConfigPushResult("deferred", detail="routing not yet active")

    assert result.applied is False
    assert result.detail == "routing not yet active"


async def test_apply_policy_validates_then_saves(service, stub_catalog) -> None:
    provider = _provider()
    stub_catalog([_model(provider, "gpt-4.1")])
    policy = _policy(RoutingStrategy.FALLBACK, {}, ["gpt-4.1"])

    result = await service.apply_policy(policy)

    assert result.applied is True


async def test_apply_policy_refuses_an_unresolvable_allowlist(
    service, stub_catalog
) -> None:
    stub_catalog([])
    policy = _policy(RoutingStrategy.FALLBACK, {}, ["gpt-4.1"])

    with pytest.raises(RoutingConfigError, match="gpt-4.1"):
        await service.apply_policy(policy)


async def test_apply_policy_never_logs_or_returns_credentials(
    service, stub_catalog, caplog
) -> None:
    credentials = CredentialService()
    provider = _provider(
        credentials_encrypted=credentials.encrypt({"api_key": SECRET})
    )
    stub_catalog([_model(provider, "gpt-4.1")])

    with caplog.at_level("DEBUG"):
        result = await service.apply_policy(
            _policy(RoutingStrategy.CHEAPEST, {}, ["gpt-4.1"])
        )

    assert result.applied is True
    assert SECRET not in caplog.text
