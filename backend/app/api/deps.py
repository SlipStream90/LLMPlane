"""Shared FastAPI dependencies: auth, session, pagination.

`get_current_project` is the single authentication gate for `/api/v1/*`
(ARCHITECTURE.md 4.1). Every route module depends on it — either directly or
through the router-level dependency wired in `api/v1/__init__.py` — except
`/api/v1/auth/bootstrap-key`, which cannot (there is no key yet) and instead
verifies the bootstrap token.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ProblemException
from app.core.security import constant_time_compare
from app.models.tenancy import APIKey, Project
from app.repositories.tenancy import APIKeyRepository

#: `auto_error=False` so a missing header produces our RFC 7807 body rather
#: than Starlette's default JSON shape.
bearer_scheme = HTTPBearer(auto_error=False, description="Project API key")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class AuthContext:
    """The authenticated caller: a project plus the key that identified it."""

    __slots__ = ("api_key", "project")

    def __init__(self, project: Project, api_key: APIKey) -> None:
        self.project = project
        self.api_key = api_key

    @property
    def project_id(self):
        return self.project.id

    def has_scope(self, scope: str) -> bool:
        return scope in (self.api_key.scopes or [])


async def get_auth_context(
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> AuthContext:
    if credentials is None or not credentials.credentials:
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing 'Authorization: Bearer {project_api_key}' header.",
            type_="https://llmplane.dev/problems/unauthenticated",
        )

    repo = APIKeyRepository(session)
    api_key = await repo.resolve(credentials.credentials)
    if api_key is None:
        # One message for "no such key", "revoked" and "wrong key" alike — an
        # error that distinguishes them is an oracle for key enumeration.
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED,
            "The provided API key is not valid.",
            type_="https://llmplane.dev/problems/unauthenticated",
        )

    await repo.touch_last_used(api_key)
    project = await session.get(Project, api_key.project_id)
    if project is None:
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED,
            "The project for this API key no longer exists.",
            type_="https://llmplane.dev/problems/unauthenticated",
        )
    return AuthContext(project, api_key)


AuthDep = Annotated[AuthContext, Depends(get_auth_context)]


async def get_current_project(auth: AuthDep) -> Project:
    return auth.project


ProjectDep = Annotated[Project, Depends(get_current_project)]


async def require_admin_scope(auth: AuthDep) -> AuthContext:
    """Guard for key/project management routes.

    Alpha has two coarse scopes (`gateway`, `admin`) and no finer-grained
    permissions — ADR-002 defers real RBAC to Phase 3.
    """
    if not auth.has_scope("admin"):
        raise ProblemException(
            status.HTTP_403_FORBIDDEN,
            "This operation requires an API key with the 'admin' scope.",
            type_="https://llmplane.dev/problems/forbidden",
        )
    return auth


AdminDep = Annotated[AuthContext, Depends(require_admin_scope)]


async def verify_bootstrap_token(
    settings: SettingsDep,
    x_bootstrap_token: Annotated[str | None, Header(alias="X-Bootstrap-Token")] = None,
) -> None:
    """Bootstrap-only auth for creating the very first API key (ADR-002)."""
    if not x_bootstrap_token or not constant_time_compare(
        x_bootstrap_token, settings.bootstrap_admin_token
    ):
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED,
            "A valid 'X-Bootstrap-Token' header is required for this endpoint.",
            type_="https://llmplane.dev/problems/unauthenticated",
        )


class Pagination:
    """Cursor pagination params, clamped to the configured maximum."""

    def __init__(
        self,
        cursor: Annotated[str | None, Query(description="Opaque cursor")] = None,
        limit: Annotated[int | None, Query(ge=1, le=200)] = None,
    ) -> None:
        settings = get_settings()
        self.cursor = cursor
        self.limit = min(limit or settings.default_page_limit, settings.max_page_limit)


PaginationDep = Annotated[Pagination, Depends(Pagination)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
