"""Playground comparison repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.playground import PlaygroundComparison, PlaygroundResponse
from app.repositories.base import BaseRepository


class PlaygroundComparisonRepository(BaseRepository[PlaygroundComparison]):
    model = PlaygroundComparison

    async def get_with_responses(
        self, comparison_id: uuid.UUID, project_id: uuid.UUID
    ) -> PlaygroundComparison | None:
        stmt = (
            select(PlaygroundComparison)
            .where(
                PlaygroundComparison.id == comparison_id,
                PlaygroundComparison.project_id == project_id,
            )
            .options(selectinload(PlaygroundComparison.responses))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class PlaygroundResponseRepository(BaseRepository[PlaygroundResponse]):
    model = PlaygroundResponse

    async def bulk_add(
        self, responses: list[PlaygroundResponse]
    ) -> list[PlaygroundResponse]:
        self.session.add_all(responses)
        await self.session.flush()
        return responses

    async def get_for_project(
        self, response_id: uuid.UUID, project_id: uuid.UUID
    ) -> PlaygroundResponse | None:
        stmt = (
            select(PlaygroundResponse)
            .join(
                PlaygroundComparison,
                PlaygroundComparison.id == PlaygroundResponse.comparison_id,
            )
            .where(
                PlaygroundResponse.id == response_id,
                PlaygroundComparison.project_id == project_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
