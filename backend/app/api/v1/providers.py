"""Providers API (T016): CRUD, health check, model catalog."""

from __future__ import annotations

import dataclasses
import uuid

from fastapi import APIRouter, status

from app.api.deps import ProjectDep, SessionDep
from app.core.errors import ConflictProblem, NotFoundProblem
from app.models.enums import LOCAL_PROVIDER_TYPES, ProviderType
from app.models.provider import Provider, ProviderModel
from app.plugins.registry import get_plugin_registry
from app.repositories.provider import ProviderModelRepository, ProviderRepository
from app.schemas.provider import (
    BulkModelConfirm,
    ModelDiscoveryOut,
    PluginManifestOut,
    ProviderCreate,
    ProviderHealthOut,
    ProviderModelCreate,
    ProviderModelOut,
    ProviderOut,
    ProviderUpdate,
)
from app.services.credential_service import CredentialService
from app.services.provider_health_service import ProviderHealthService

router = APIRouter(prefix="/providers", tags=["providers"])


def _to_out(provider: Provider, credentials: CredentialService) -> ProviderOut:
    """Serialise a provider with its credential masked to the last 4 chars.

    This function is the only place a provider becomes a response body, which
    is what makes "credentials never leave the server" checkable rather than
    aspirational.
    """
    out = ProviderOut.model_validate(provider)
    out.has_credentials = bool(provider.credentials_encrypted)
    out.credential_hint = credentials.masked_hint(provider.credentials_encrypted)
    return out


@router.get("", response_model=list[ProviderOut], summary="List providers")
async def list_providers(
    session: SessionDep, project: ProjectDep, active_only: bool = False
) -> list[ProviderOut]:
    credentials = CredentialService()
    providers = await ProviderRepository(session).list_for_project(
        project.id, active_only=active_only
    )
    return [_to_out(p, credentials) for p in providers]


@router.get(
    "/model-catalog",
    response_model=list[ProviderModelOut],
    summary="All models across every provider in the project",
)
async def list_all_models(
    session: SessionDep, project: ProjectDep
) -> list[ProviderModelOut]:
    """Declared before `/{provider_id}` on purpose: FastAPI matches routes in
    declaration order, so a literal path that could also parse as a path
    parameter has to come first."""
    models = await ProviderModelRepository(session).list_for_project(project.id)
    return [ProviderModelOut.model_validate(m) for m in models]


@router.get(
    "/plugins",
    response_model=list[PluginManifestOut],
    summary="List registered provider plugins",
)
async def list_plugins() -> list[PluginManifestOut]:
    """Declared before `/{provider_id}` for the same route-ordering reason as
    `/model-catalog` above. Feeds the wizard's provider-type picker."""
    manifests = get_plugin_registry().list_manifests()
    return [PluginManifestOut(**dataclasses.asdict(manifest)) for manifest in manifests]


@router.post(
    "",
    response_model=ProviderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a provider",
)
async def create_provider(
    payload: ProviderCreate, session: SessionDep, project: ProjectDep
) -> ProviderOut:
    repo = ProviderRepository(session)
    existing = await repo.list_for_project(project.id)
    if any(p.display_name == payload.display_name for p in existing):
        raise ConflictProblem(
            f"A provider named '{payload.display_name}' already exists in this project."
        )

    if payload.provider_type == ProviderType.CUSTOM:
        # payload.plugin_id presence is already guaranteed by ProviderCreate's
        # validator; resolving it against the live registry is the one check
        # that belongs at this layer, since only the route layer already
        # holds a registry handle (schemas/provider.py's docstring on
        # plugin_id explains why this isn't duplicated at the schema layer).
        if get_plugin_registry().get(payload.plugin_id) is None:  # type: ignore[arg-type]
            raise ConflictProblem(
                f"No registered plugin with id '{payload.plugin_id}'."
            )

    credentials = CredentialService()
    blob = None
    creds = credentials.build(payload.api_key, payload.extra_credentials)
    if creds:
        blob = credentials.encrypt(creds)

    provider = await repo.add(
        Provider(
            project_id=project.id,
            provider_type=payload.provider_type,
            display_name=payload.display_name,
            credentials_encrypted=blob,
            base_url=payload.base_url,
            plugin_id=payload.plugin_id,
            is_active=True,
        )
    )
    return _to_out(provider, credentials)


@router.get("/{provider_id}", response_model=ProviderOut, summary="Get provider")
async def get_provider(
    provider_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> ProviderOut:
    provider = await ProviderRepository(session).get(provider_id, project_id=project.id)
    if provider is None:
        raise NotFoundProblem("Provider", provider_id)
    return _to_out(provider, CredentialService())


@router.patch("/{provider_id}", response_model=ProviderOut, summary="Update provider")
async def update_provider(
    provider_id: uuid.UUID,
    payload: ProviderUpdate,
    session: SessionDep,
    project: ProjectDep,
) -> ProviderOut:
    repo = ProviderRepository(session)
    provider = await repo.get(provider_id, project_id=project.id)
    if provider is None:
        raise NotFoundProblem("Provider", provider_id)

    credentials = CredentialService()
    if payload.display_name is not None:
        provider.display_name = payload.display_name
    if payload.base_url is not None:
        provider.base_url = payload.base_url
    if payload.is_active is not None:
        provider.is_active = payload.is_active
    if payload.api_key or payload.extra_credentials:
        provider.credentials_encrypted = credentials.merge(
            provider.credentials_encrypted,
            api_key=payload.api_key,
            extra=payload.extra_credentials,
        )
    await session.flush()
    return _to_out(provider, credentials)


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete provider",
)
async def delete_provider(
    provider_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> None:
    repo = ProviderRepository(session)
    provider = await repo.get(provider_id, project_id=project.id)
    if provider is None:
        raise NotFoundProblem("Provider", provider_id)
    if provider.provider_type in LOCAL_PROVIDER_TYPES:
        # Local providers are owned by a Deployment; deleting one out from
        # under a running container would orphan it (FK is RESTRICT anyway).
        raise ConflictProblem(
            "This provider was created by a local deployment. Delete the "
            "deployment instead."
        )
    await repo.delete(provider)


@router.post(
    "/{provider_id}/health-check",
    response_model=ProviderHealthOut,
    summary="Run an immediate health check",
)
async def health_check(
    provider_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> ProviderHealthOut:
    provider = await ProviderRepository(session).get(provider_id, project_id=project.id)
    if provider is None:
        raise NotFoundProblem("Provider", provider_id)

    result = await ProviderHealthService(session).check(provider)
    return ProviderHealthOut(
        provider_id=provider.id,
        health_status=result.status,
        latency_ms=result.latency_ms,
        checked_at=result.checked_at,
        detail=result.detail,
    )


@router.get(
    "/{provider_id}/models",
    response_model=list[ProviderModelOut],
    summary="List models registered under a provider",
)
async def list_provider_models(
    provider_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> list[ProviderModelOut]:
    provider = await ProviderRepository(session).get(provider_id, project_id=project.id)
    if provider is None:
        raise NotFoundProblem("Provider", provider_id)
    models = await ProviderModelRepository(session).list_for_provider(provider_id)
    return [ProviderModelOut.model_validate(m) for m in models]


@router.post(
    "/{provider_id}/models",
    response_model=ProviderModelOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a model under a provider",
)
async def create_provider_model(
    provider_id: uuid.UUID,
    payload: ProviderModelCreate,
    session: SessionDep,
    project: ProjectDep,
) -> ProviderModelOut:
    """Register a catalog entry.

    Pricing and context window are supplied by the operator: alpha does not
    live-sync provider catalogs (PRD 3.1), and inventing pricing would poison
    every cost aggregate that reads it.
    """
    provider = await ProviderRepository(session).get(provider_id, project_id=project.id)
    if provider is None:
        raise NotFoundProblem("Provider", provider_id)

    repo = ProviderModelRepository(session)
    model = await _create_model(repo, provider_id, payload)
    return ProviderModelOut.model_validate(model)


async def _create_model(
    repo: ProviderModelRepository, provider_id: uuid.UUID, payload: ProviderModelCreate
) -> ProviderModel:
    """Shared insert path for a single `ProviderModel` row.

    Factored out of `create_provider_model` so the wizard's bulk-confirm
    endpoint (`POST /providers/{id}/models/bulk-confirm`) reuses the exact
    same validation/persistence logic in a loop rather than duplicating it.
    """
    if any(m.model_id == payload.model_id for m in await repo.list_for_provider(provider_id)):
        raise ConflictProblem(
            f"Model '{payload.model_id}' is already registered under this provider."
        )
    return await repo.add(
        ProviderModel(
            provider_id=provider_id,
            model_id=payload.model_id,
            display_name=payload.display_name or payload.model_id,
            context_window=payload.context_window,
            input_price_per_1m=payload.input_price_per_1m,
            output_price_per_1m=payload.output_price_per_1m,
            capabilities=payload.capabilities,
        )
    )


@router.post(
    "/{provider_id}/discover-models",
    response_model=ModelDiscoveryOut,
    summary="Discover models via the provider's plugin (read-only)",
)
async def discover_models(
    provider_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> ModelDiscoveryOut:
    """Read-only model catalog discovery against the provider's own API.

    Does **not** persist anything — the wizard reviews/edits the result and
    calls `bulk-confirm` (below) to actually register the chosen models.
    """
    provider = await ProviderRepository(session).get(provider_id, project_id=project.id)
    if provider is None:
        raise NotFoundProblem("Provider", provider_id)
    if not provider.plugin_id:
        raise NotFoundProblem("Plugin for provider", provider_id)

    plugin = get_plugin_registry().get(provider.plugin_id)
    if plugin is None:
        raise NotFoundProblem("Plugin", provider.plugin_id)

    credentials = CredentialService()
    api_key = credentials.api_key_of(provider.credentials_encrypted)
    discovered = await plugin.list_models(base_url=provider.base_url, api_key=api_key)
    return ModelDiscoveryOut(
        provider_id=provider.id,
        models=[
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "context_window": m.context_window,
                "capabilities": m.capabilities,
            }
            for m in discovered
        ],
    )


@router.post(
    "/{provider_id}/models/bulk-confirm",
    response_model=list[ProviderModelOut],
    status_code=status.HTTP_201_CREATED,
    summary="Register the wizard's reviewed model selection",
)
async def bulk_confirm_models(
    provider_id: uuid.UUID,
    payload: BulkModelConfirm,
    session: SessionDep,
    project: ProjectDep,
) -> list[ProviderModelOut]:
    """Wizard's final step: persist the user-reviewed subset of
    `discover-models`' output. Loops over the same single-model insert path
    `POST /providers/{id}/models` uses (`_create_model`) — no new persistence
    logic, per R2/R4 additive-only.
    """
    provider = await ProviderRepository(session).get(provider_id, project_id=project.id)
    if provider is None:
        raise NotFoundProblem("Provider", provider_id)

    repo = ProviderModelRepository(session)
    created = [
        await _create_model(repo, provider_id, model_payload)
        for model_payload in payload.models
    ]
    return [ProviderModelOut.model_validate(m) for m in created]


