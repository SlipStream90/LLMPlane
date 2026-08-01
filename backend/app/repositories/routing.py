"""RoutingPolicy repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update

from app.models.routing import RoutingPolicy
from app.repositories.base import BaseRepository


class RoutingPolicyRepository(BaseRepository[RoutingPolicy]):
    model = RoutingPolicy

    async def list_for_project(self, project_id: uuid.UUID) -> list[RoutingPolicy]:
        return await self.list_all(project_id=project_id)

    async def get_active(self, project_id: uuid.UUID) -> RoutingPolicy | None:
        stmt = select(RoutingPolicy).where(
            RoutingPolicy.project_id == project_id, RoutingPolicy.is_active.is_(True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def activate(self, policy: RoutingPolicy) -> RoutingPolicy:
        """Make `policy` the single active policy for its project.

        Deactivate-then-activate in one transaction; the partial unique index
        on `(project_id) WHERE is_active` is the real guard against two active
        policies under concurrency, this ordering just avoids tripping it.
        """
        await self.session.execute(
            update(RoutingPolicy)
            .where(
                RoutingPolicy.project_id == policy.project_id,
                RoutingPolicy.id != policy.id,
                RoutingPolicy.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await self.session.flush()
        policy.is_active = True
        await self.session.flush()
        return policy
