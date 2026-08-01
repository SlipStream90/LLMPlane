"""Organization / Project / APIKey repositories."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.security import verify_api_key
from app.models.tenancy import APIKey, Organization, Project
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    model = Organization

    async def get_or_create_default(
        self, name: str = "Default Organization"
    ) -> Organization:
        """ADR-002: exactly one seeded organization row in alpha."""
        existing = (
            await self.session.execute(select(Organization).limit(1))
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        return await self.add(Organization(name=name))


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def get_by_slug(self, slug: str) -> Project | None:
        stmt = select(Project).where(Project.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class APIKeyRepository(BaseRepository[APIKey]):
    model = APIKey

    async def list_for_project(self, project_id: uuid.UUID) -> list[APIKey]:
        return await self.list_all(project_id=project_id)

    async def resolve(self, raw_key: str) -> APIKey | None:
        """Find the live key matching `raw_key`, or None.

        Narrowing by the indexed non-secret `key_prefix` keeps this to a small
        candidate set; the actual decision is always the argon2id verify. A
        revoked key never resolves.
        """
        prefix = raw_key[:8]
        stmt = select(APIKey).where(
            APIKey.key_prefix == prefix, APIKey.revoked_at.is_(None)
        )
        candidates = (await self.session.execute(stmt)).scalars().all()
        for candidate in candidates:
            if verify_api_key(raw_key, candidate.key_hash):
                return candidate
        return None

    async def touch_last_used(self, api_key: APIKey) -> None:
        api_key.last_used_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def revoke(self, api_key: APIKey) -> APIKey:
        if api_key.revoked_at is None:
            api_key.revoked_at = datetime.now(timezone.utc)
            await self.session.flush()
        return api_key

    async def count_active(self) -> int:
        stmt = select(APIKey).where(APIKey.revoked_at.is_(None))
        return len((await self.session.execute(stmt)).scalars().all())
