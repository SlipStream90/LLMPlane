"""Shared FastAPI dependencies: auth, session, pagination.

`get_current_project` is the single authentication gate for `/api/v1/*`
(ARCHITECTURE.md 4.1). Every route module depends on it — either directly or
through the router-level dependency wired in `api/v1/__init__.py` — except
`/api/v1/auth/bootstrap-key`, which cannot (there is no key yet) and instead
verifies the bootstrap token.

Supports two auth methods:
  1. API key: `Authorization: Bearer llcp_xxxx_...`
  2. JWT session token: from cookie `llcp_session` or `Authorization: Bearer <jwt>`
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ProblemException
from app.core.security import constant_time_compare, decode_access_token
from app.models.tenancy import APIKey, Project
from app.models.user import User
from app.repositories.tenancy import APIKeyRepository

#: `auto_error=False` so a missing header produces our RFC 7807 body rather
#: than Starlette's default JSON shape.
bearer_scheme = HTTPBearer(auto_error=False, description="Project API key or JWT session token")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class AuthContext:
    """The authenticated caller: a project plus the key that identified it.
    For OAuth users, api_key may be None and user will be set instead."""

    __slots__ = ("api_key", "project", "user")

    def __init__(self, project: Project, api_key: APIKey | None = None, user: User | None = None) -> None:
        self.project = project
        self.api_key = api_key
        self.user = user

    @property
    def project_id(self):
        return self.project.id

    def has_scope(self, scope: str) -> bool:
        if self.api_key:
            return scope in (self.api_key.scopes or [])
        # OAuth users get admin scope by default (they are the account owner)
        if self.user:
            return True
        return False


def _extract_bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    """Extract bearer token from Authorization header."""
    if credentials and credentials.credentials:
        return credentials.credentials
    return None


def _extract_session_token(request: Request) -> str | None:
    """Extract session token from cookie."""
    return request.cookies.get("llcp_session")


async def get_auth_context(
    session: SessionDep,
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> AuthContext:
    """Authenticate via API key (Bearer token) or JWT session cookie."""
    settings = get_settings()

    # Try JWT session token first (from cookie or header)
    jwt_token = _extract_session_token(request) or _extract_bearer_token(credentials)
    if jwt_token and "." in jwt_token:  # JWT tokens contain dots
        payload = decode_access_token(jwt_token, settings.fernet_secret_key)
        if payload:
            user_id = payload.get("sub")
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                # Load or create default project for OAuth user
                project = None
                if user.default_project_id:
                    project = await session.get(Project, user.default_project_id)
                if project is None:
                    # Fallback: get or create default project
                    from app.repositories.tenancy import OrganizationRepository, ProjectRepository
                    orgs = OrganizationRepository(session)
                    projects = ProjectRepository(session)
                    org = await orgs.get_or_create_default()
                    project = await projects.get_by_slug("default")
                    if project is None:
                        project = await projects.add(
                            Project(
                                organization_id=org.id,
                                name="Default Project",
                                slug="default",
                            )
                        )
                    user.default_project_id = project.id
                    await session.commit()

                # Create a virtual API key for OAuth users (admin scope)
                virtual_key = APIKey(
                    project_id=project.id,
                    name="oauth-session",
                    key_prefix="oauth",
                    key_hash="",
                    scopes=["admin", "gateway"],
                )
                return AuthContext(project=project, api_key=virtual_key, user=user)

    # Fall back to API key auth
    token = _extract_bearer_token(credentials)
    if not token:
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing 'Authorization: Bearer {token}' header. Provide an API key or log in via OAuth.",
            type_="https://llmplane.dev/problems/unauthenticated",
        )

    repo = APIKeyRepository(session)
    api_key = await repo.resolve(token)
    if api_key is None:
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
