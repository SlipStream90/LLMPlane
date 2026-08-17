"""OAuth authentication routes.

Provides GitHub and Google OAuth login flow:
1. GET /auth/oauth/{provider}/login   — redirect to provider
2. GET /auth/oauth/{provider}/callback — handle callback, create user, return JWT
3. GET /auth/me                       — current user info
4. POST /auth/logout                  — invalidate session (client-side)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import ProblemException
from app.core.security import create_access_token, decode_access_token
from app.models.user import User
from app.repositories.tenancy import OrganizationRepository, ProjectRepository
from app.services.oauth_service import (
    exchange_github_code,
    exchange_google_code,
    get_github_authorize_url,
    get_google_authorize_url,
)

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_PROVIDERS = {"github", "google"}
COOKIE_NAME = "llcp_session"


def _get_session_token(request: Request) -> str | None:
    """Extract session token from cookie or Authorization header."""
    # Try cookie first
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    # Try Authorization header
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


@router.get(
    "/oauth/{provider}/login",
    summary="Initiate OAuth login",
    responses={
        307: {"description": "Redirect to OAuth provider"},
        400: {"description": "Invalid provider"},
    },
)
async def oauth_login(
    provider: str,
    response: Response,
    redirect_uri: str = Query(
        default="",
        description="Post-login redirect URL (defaults to frontend root)",
    ),
):
    """Redirect the user to the OAuth provider's authorization page."""
    if provider not in OAUTH_PROVIDERS:
        raise ProblemException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported OAuth provider: {provider}. Use 'github' or 'google'.",
            type_="https://llmplane.dev/problems/bad-request",
        )

    settings = get_settings()

    if provider == "github":
        client_id = settings.github_client_id
        callback_base = settings.oauth_callback_base_url
        full_redirect_uri = f"{callback_base}/api/v1/auth/oauth/github/callback"
        url, state = get_github_authorize_url(full_redirect_uri, client_id)
    else:
        client_id = settings.google_client_id
        callback_base = settings.oauth_callback_base_url
        full_redirect_uri = f"{callback_base}/api/v1/auth/oauth/google/callback"
        url, state = get_google_authorize_url(full_redirect_uri, client_id)

    # Store state in cookie for CSRF verification
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=600,  # 10 minutes
    )

    response.headers["Location"] = url
    response.status_code = status.HTTP_307_REDIRECT
    return response


@router.get(
    "/oauth/{provider}/callback",
    summary="OAuth callback handler",
    responses={
        200: {"description": "Login successful, JWT token returned"},
        400: {"description": "Invalid state or provider error"},
    },
)
async def oauth_callback(
    provider: str,
    response: Response,
    code: str = Query(...),
    state: str = Query(...),
    oauth_state: str = Header(alias="Cookie", convert_underscores=False),
    session: AsyncSession = Depends(get_session),
):
    """Handle OAuth callback: verify state, exchange code, create/find user, return JWT."""
    if provider not in OAUTH_PROVIDERS:
        raise ProblemException(
            status.HTTP_400_BAD_REQUEST,
            f"Invalid provider: {provider}",
            type_="https://llmplane.dev/problems/bad-request",
        )

    settings = get_settings()

    # Verify CSRF state
    # Parse the cookie header to get oauth_state
    actual_state = None
    for part in (oauth_state or "").split(";"):
        part = part.strip()
        if part.startswith("oauth_state="):
            actual_state = part.split("=", 1)[1]
            break

    if not actual_state or actual_state != state:
        raise ProblemException(
            status.HTTP_400_BAD_REQUEST,
            "Invalid or expired OAuth state. Please try logging in again.",
            type_="https://llmplane.dev/problems/bad-request",
        )

    # Exchange code for user info
    if provider == "github":
        callback_base = settings.oauth_callback_base_url
        full_redirect_uri = f"{callback_base}/api/v1/auth/oauth/github/callback"
        user_info = await exchange_github_code(
            code, settings.github_client_id, settings.github_client_secret
        )
    else:
        callback_base = settings.oauth_callback_base_url
        full_redirect_uri = f"{callback_base}/api/v1/auth/oauth/google/callback"
        user_info = await exchange_google_code(
            code, settings.google_client_id, settings.google_client_secret, full_redirect_uri
        )

    if not user_info or not user_info.get("email"):
        raise ProblemException(
            status.HTTP_400_BAD_REQUEST,
            "Failed to authenticate with OAuth provider. Please try again.",
            type_="https://llmplane.dev/problems/bad-request",
        )

    # Find or create user
    result = await session.execute(
        select(User).where(
            User.provider == provider,
            User.provider_user_id == user_info["provider_user_id"],
        )
    )
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc).isoformat()

    if user is None:
        # Check if email already exists with a different provider
        result = await session.execute(
            select(User).where(User.email == user_info["email"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Link the new provider to the existing user
            existing.provider = provider
            existing.provider_user_id = user_info["provider_user_id"]
            existing.name = user_info.get("name") or existing.name
            existing.avatar_url = user_info.get("avatar_url") or existing.avatar_url
            existing.last_login_at = now
            user = existing
        else:
            # Create new user
            user = User(
                email=user_info["email"],
                name=user_info.get("name"),
                avatar_url=user_info.get("avatar_url"),
                provider=provider,
                provider_user_id=user_info["provider_user_id"],
                last_login_at=now,
            )
            session.add(user)

            # Auto-create default org/project for first user
            orgs = OrganizationRepository(session)
            projects = ProjectRepository(session)
            org = await orgs.get_or_create_default()

            # Check if this is the first user — if so, create a default project
            from sqlalchemy import func

            count_result = await session.execute(select(func.count()).select_from(User))
            user_count = count_result.scalar() or 0

            if user_count <= 1:
                # First user gets a default project
                project = await projects.add(
                    __import__("app.models.tenancy", fromlist=["Project"]).Project(
                        organization_id=org.id,
                        name="Default Project",
                        slug="default",
                    )
                )
                user.default_project_id = project.id

            user.last_login_at = now
    else:
        # Update existing user's last login
        user.last_login_at = now
        if user_info.get("name"):
            user.name = user_info["name"]
        if user_info.get("avatar_url"):
            user.avatar_url = user_info["avatar_url"]

    await session.commit()
    await session.refresh(user)

    # Generate JWT
    token = create_access_token(
        user_id=user.id,
        email=user.email,
        secret_key=settings.fernet_secret_key,  # Using fernet key as JWT secret
    )

    # Set session cookie
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
        path="/",
    )

    # Clear oauth_state cookie
    response.delete_cookie("oauth_state")

    # Return token in body for API clients, cookie for browser
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "provider": user.provider,
        },
    }


@router.get(
    "/me",
    summary="Get current user info",
    tags=["auth"],
)
async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Return the current authenticated user's profile."""
    token = _get_session_token(request)
    if not token:
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated. Please log in.",
            type_="https://llmplane.dev/problems/unauthenticated",
        )

    settings = get_settings()
    payload = decode_access_token(token, settings.fernet_secret_key)
    if not payload:
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired session. Please log in again.",
            type_="https://llmplane.dev/problems/unauthenticated",
        )

    user_id = payload.get("sub")
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ProblemException(
            status.HTTP_401_UNAUTHORIZED,
            "User not found.",
            type_="https://llmplane.dev/problems/unauthenticated",
        )

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "provider": user.provider,
        "default_project_id": str(user.default_project_id) if user.default_project_id else None,
    }


@router.post(
    "/logout",
    summary="Log out (clear session cookie)",
    tags=["auth"],
)
async def logout(response: Response):
    """Clear the session cookie. Client should also clear localStorage."""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "ok"}
