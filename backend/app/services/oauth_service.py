"""OAuth service for GitHub and Google authentication.

Handles the OAuth2 flow:
1. Generate authorization URL for the provider
2. Exchange authorization code for access token
3. Fetch user profile from the provider
4. Create/update user in database
5. Generate JWT session token
"""

from __future__ import annotations

import secrets
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── GitHub OAuth ───────────────────────────────────────────────────────────

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

# ── Google OAuth ───────────────────────────────────────────────────────────

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# CSRF state token (stored in cookie, verified on callback)
OAUTH_STATE_SECRET = secrets.token_urlsafe(32)


def get_github_authorize_url(redirect_uri: str, client_id: str) -> tuple[str, str]:
    """Generate GitHub OAuth authorization URL. Returns (url, state)."""
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "read:user user:email",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GITHUB_AUTHORIZE_URL}?{query}", state


def get_google_authorize_url(redirect_uri: str, client_id: str) -> tuple[str, str]:
    """Generate Google OAuth authorization URL. Returns (url, state)."""
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTHORIZE_URL}?{query}", state


async def exchange_github_code(
    code: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any] | None:
    """Exchange GitHub authorization code for access token + user profile."""
    async with httpx.AsyncClient(timeout=15) as client:
        # Exchange code for token
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            logger.error("GitHub token exchange failed: %s", token_resp.text)
            return None

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            logger.error("No access_token in GitHub response")
            return None

        # Fetch user profile
        user_resp = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        if user_resp.status_code != 200:
            logger.error("GitHub user fetch failed: %s", user_resp.text)
            return None

        user_data = user_resp.json()

        # Fetch primary email
        email_resp = await client.get(
            GITHUB_EMAILS_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        email = user_data.get("email")
        if not email and email_resp.status_code == 200:
            emails = email_resp.json()
            for e in emails:
                if e.get("primary"):
                    email = e.get("email")
                    break
            if not email and emails:
                email = emails[0].get("email")

        return {
            "provider": "github",
            "provider_user_id": str(user_data.get("id")),
            "email": email,
            "name": user_data.get("name") or user_data.get("login"),
            "avatar_url": user_data.get("avatar_url"),
        }


async def exchange_google_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any] | None:
    """Exchange Google authorization code for access token + user profile."""
    async with httpx.AsyncClient(timeout=15) as client:
        # Exchange code for token
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            logger.error("Google token exchange failed: %s", token_resp.text)
            return None

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            logger.error("No access_token in Google response")
            return None

        # Fetch user profile
        user_resp = await client.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_resp.status_code != 200:
            logger.error("Google user fetch failed: %s", user_resp.text)
            return None

        user_data = user_resp.json()
        return {
            "provider": "google",
            "provider_user_id": user_data.get("id"),
            "email": user_data.get("email"),
            "name": user_data.get("name"),
            "avatar_url": user_data.get("picture"),
        }
