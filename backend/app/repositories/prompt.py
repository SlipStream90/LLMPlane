"""Prompt / PromptVersion repositories."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.prompt import Prompt, PromptVersion
from app.repositories.base import BaseRepository

#: `{{ variable_name }}` — whitespace tolerant, identifier-ish names only, so a
#: stray `{{` in prose does not become a phantom variable.
_VARIABLE_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def extract_variables(content: str) -> list[str]:
    """Ordered, de-duplicated `{{var}}` names found in a prompt body."""
    seen: dict[str, None] = {}
    for match in _VARIABLE_RE.finditer(content or ""):
        seen.setdefault(match.group(1), None)
    return list(seen)


class PromptRepository(BaseRepository[Prompt]):
    model = Prompt

    async def get_with_versions(
        self, prompt_id: uuid.UUID, project_id: uuid.UUID
    ) -> Prompt | None:
        stmt = (
            select(Prompt)
            .where(Prompt.id == prompt_id, Prompt.project_id == project_id)
            .options(selectinload(Prompt.versions))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_name(self, project_id: uuid.UUID, name: str) -> Prompt | None:
        stmt = select(Prompt).where(
            Prompt.project_id == project_id, Prompt.name == name
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class PromptVersionRepository(BaseRepository[PromptVersion]):
    model = PromptVersion

    async def list_for_prompt(self, prompt_id: uuid.UUID) -> list[PromptVersion]:
        stmt = (
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.version_number.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_version(
        self, prompt_id: uuid.UUID, version_number: int
    ) -> PromptVersion | None:
        stmt = select(PromptVersion).where(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.version_number == version_number,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def latest_version_number(self, prompt_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.max(PromptVersion.version_number), 0)).where(
            PromptVersion.prompt_id == prompt_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def create_version(
        self,
        *,
        prompt_id: uuid.UUID,
        content: str,
        system_prompt: str | None = None,
        note: str | None = None,
    ) -> PromptVersion:
        """Append a new version. Version numbers are assigned server-side and
        are monotonic per prompt — a client never chooses one."""
        next_number = await self.latest_version_number(prompt_id) + 1
        return await self.add(
            PromptVersion(
                prompt_id=prompt_id,
                version_number=next_number,
                content=content,
                variables=extract_variables(content),
                system_prompt=system_prompt,
                created_by_note=note,
            )
        )
