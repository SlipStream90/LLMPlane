"""Bootstrap authentication (T008).

Alpha has no login flow (ADR-002). The single operator calls
`POST /api/v1/auth/bootstrap-key` once with the `X-Bootstrap-Token` header to
mint the first project + admin API key; everything else authenticates with that
key.

The endpoint is idempotent-ish by design: it will create additional keys for an
existing project, but it refuses once *any* active key exists unless
`allow_additional=true` is passed — an unauthenticated-by-API-key endpoint that
can be called repeatedly to mint admin keys is a standing risk, so it closes
itself after first use.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, verify_bootstrap_token
from app.core.errors import ConflictProblem
from app.core.security import generate_api_key
from app.models.enums import ApiKeyScope
from app.models.tenancy import APIKey
from app.repositories.tenancy import (
    APIKeyRepository,
    OrganizationRepository,
    ProjectRepository,
)
from app.schemas.tenancy import (
    ApiKeyCreated,
    ApiKeyOut,
    BootstrapKeyRequest,
    BootstrapKeyResponse,
    ProjectOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/bootstrap-key",
    response_model=BootstrapKeyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bootstrap_token)],
    summary="Create the first project and admin API key",
)
async def bootstrap_key(
    payload: BootstrapKeyRequest,
    session: SessionDep,
    allow_additional: bool = Query(
        False,
        description=(
            "Permit minting another key even though active keys already exist. "
            "Requires the bootstrap token; intended for key-loss recovery."
        ),
    ),
) -> BootstrapKeyResponse:
    keys = APIKeyRepository(session)

    if not allow_additional and await keys.count_active() > 0:
        raise ConflictProblem(
            "An active API key already exists. Create further keys through "
            "POST /api/v1/projects/{project_id}/keys, or pass "
            "?allow_additional=true if the existing key was lost."
        )

    organizations = OrganizationRepository(session)
    projects = ProjectRepository(session)

    organization = await organizations.get_or_create_default()
    project = await projects.get_by_slug(payload.project_slug)
    if project is None:
        from app.models.tenancy import Project  # local import: avoids a cycle

        project = await projects.add(
            Project(
                organization_id=organization.id,
                name=payload.project_name,
                slug=payload.project_slug,
            )
        )

    raw_key, prefix, key_hash = generate_api_key(project.id)
    api_key = await keys.add(
        APIKey(
            project_id=project.id,
            name=payload.key_name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=[ApiKeyScope.ADMIN.value, ApiKeyScope.GATEWAY.value],
        )
    )

    return BootstrapKeyResponse(
        project=ProjectOut.model_validate(project),
        api_key=ApiKeyCreated(
            **ApiKeyOut.model_validate(api_key).model_dump(), key=raw_key
        ),
    )
