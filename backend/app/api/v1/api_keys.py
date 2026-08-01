"""API keys API (T015).

The raw secret is returned exactly once, at creation. Listing returns masked
records only — there is no endpoint anywhere that can reveal an existing key,
because the server does not have it (only the argon2id hash).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminDep, SessionDep
from app.core.errors import NotFoundProblem
from app.core.security import generate_api_key
from app.models.tenancy import APIKey
from app.repositories.tenancy import APIKeyRepository
from app.schemas.tenancy import ApiKeyCreate, ApiKeyCreated, ApiKeyOut

router = APIRouter(prefix="/projects/{project_id}/keys", tags=["api-keys"])


def _assert_own_project(auth: AdminDep, project_id: uuid.UUID) -> None:
    if auth.project.id != project_id:
        raise NotFoundProblem("Project", project_id)


@router.get("", response_model=list[ApiKeyOut], summary="List API keys (masked)")
async def list_keys(
    project_id: uuid.UUID, session: SessionDep, auth: AdminDep
) -> list[ApiKeyOut]:
    _assert_own_project(auth, project_id)
    keys = await APIKeyRepository(session).list_for_project(project_id)
    return [ApiKeyOut.model_validate(k) for k in keys]


@router.post(
    "",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key (raw secret returned once)",
)
async def create_key(
    project_id: uuid.UUID,
    payload: ApiKeyCreate,
    session: SessionDep,
    auth: AdminDep,
) -> ApiKeyCreated:
    _assert_own_project(auth, project_id)
    raw_key, prefix, key_hash = generate_api_key(project_id)
    api_key = await APIKeyRepository(session).add(
        APIKey(
            project_id=project_id,
            name=payload.name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=[s.value for s in payload.scopes],
            rate_limit_rpm=payload.rate_limit_rpm,
            quota_monthly_usd=payload.quota_monthly_usd,
        )
    )
    return ApiKeyCreated(**ApiKeyOut.model_validate(api_key).model_dump(), key=raw_key)


@router.delete(
    "/{key_id}",
    response_model=ApiKeyOut,
    summary="Revoke API key",
)
async def revoke_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    session: SessionDep,
    auth: AdminDep,
) -> ApiKeyOut:
    """Revoke (never hard-delete).

    A deleted key would take its `request` attribution rows with it; revocation
    keeps the audit trail intact while making the credential unusable
    immediately — `APIKeyRepository.resolve` filters on `revoked_at IS NULL`.
    """
    _assert_own_project(auth, project_id)
    repo = APIKeyRepository(session)
    api_key = await repo.get(key_id, project_id=project_id)
    if api_key is None:
        raise NotFoundProblem("API key", key_id)
    return ApiKeyOut.model_validate(await repo.revoke(api_key))
