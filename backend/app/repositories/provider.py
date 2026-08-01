"""Provider and ProviderModel repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.enums import ProviderType
from app.models.provider import Provider, ProviderModel
from app.repositories.base import BaseRepository


class ProviderRepository(BaseRepository[Provider]):
    model = Provider

    async def list_for_project(
        self, project_id: uuid.UUID, *, active_only: bool = False
    ) -> list[Provider]:
        stmt = (
            select(Provider)
            .where(Provider.project_id == project_id)
            .options(selectinload(Provider.models))
            .order_by(Provider.created_at.desc())
        )
        if active_only:
            stmt = stmt.where(Provider.is_active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_with_models(
        self, provider_id: uuid.UUID, project_id: uuid.UUID
    ) -> Provider | None:
        stmt = (
            select(Provider)
            .where(Provider.id == provider_id, Provider.project_id == project_id)
            .options(selectinload(Provider.models))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_type(
        self, project_id: uuid.UUID, provider_type: ProviderType
    ) -> list[Provider]:
        stmt = select(Provider).where(
            Provider.project_id == project_id, Provider.provider_type == provider_type
        )
        return list((await self.session.execute(stmt)).scalars().all())


class ProviderModelRepository(BaseRepository[ProviderModel]):
    model = ProviderModel

    async def list_for_provider(self, provider_id: uuid.UUID) -> list[ProviderModel]:
        stmt = (
            select(ProviderModel)
            .where(ProviderModel.provider_id == provider_id)
            .order_by(ProviderModel.model_id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_project(self, project_id: uuid.UUID) -> list[ProviderModel]:
        stmt = (
            select(ProviderModel)
            .join(Provider, Provider.id == ProviderModel.provider_id)
            .where(Provider.project_id == project_id)
            .options(selectinload(ProviderModel.provider))
            .order_by(ProviderModel.model_id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_model_id(
        self, project_id: uuid.UUID, model_id: str
    ) -> ProviderModel | None:
        """Resolve a user-facing `model_id` (what the gateway is called with)
        to the catalog row inside this project."""
        stmt = (
            select(ProviderModel)
            .join(Provider, Provider.id == ProviderModel.provider_id)
            .where(
                Provider.project_id == project_id,
                ProviderModel.model_id == model_id,
            )
            .options(selectinload(ProviderModel.provider))
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_many(
        self, project_id: uuid.UUID, ids: list[uuid.UUID]
    ) -> list[ProviderModel]:
        if not ids:
            return []
        stmt = (
            select(ProviderModel)
            .join(Provider, Provider.id == ProviderModel.provider_id)
            .where(Provider.project_id == project_id, ProviderModel.id.in_(ids))
            .options(selectinload(ProviderModel.provider))
        )
        return list((await self.session.execute(stmt)).scalars().all())
