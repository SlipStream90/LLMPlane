"""Repository base: project-scoped CRUD and cursor pagination.

Every aggregate root gets one repository class. Routes never build queries
inline — they call repositories, which is what keeps `backend` splittable into
services later without a rewrite (ARCHITECTURE.md 1).

Pagination is keyset ("cursor") based on ``(created_at DESC, id DESC)``, per
api-contracts.md 2. Offset pagination is deliberately not used: the two big
tables (`request`, `gpu_sample`) are append-heavy, and OFFSET degrades linearly
while a keyset scan stays flat.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationProblem
from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


@dataclass(frozen=True)
class Page(Generic[ModelT]):
    data: Sequence[ModelT]
    next_cursor: str | None


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        ts_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(ts_str), uuid.UUID(id_str)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        # A malformed cursor is client error, not a 500.
        raise ValidationProblem("Malformed pagination cursor.") from exc


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]
    #: Timestamp column used for keyset ordering. `Request`/`GpuSample`
    #: override this with their own event-time column.
    order_column_name: str = "created_at"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -- helpers ----------------------------------------------------------
    @property
    def _order_col(self) -> Any:
        return getattr(self.model, self.order_column_name)

    def _scoped(self, project_id: uuid.UUID | None) -> Select[Any]:
        stmt = select(self.model)
        if project_id is not None and hasattr(self.model, "project_id"):
            stmt = stmt.where(self.model.project_id == project_id)  # type: ignore[attr-defined]
        return stmt

    # -- reads ------------------------------------------------------------
    async def get(
        self, row_id: uuid.UUID, *, project_id: uuid.UUID | None = None
    ) -> ModelT | None:
        stmt = self._scoped(project_id).where(self.model.id == row_id)  # type: ignore[attr-defined]
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        project_id: uuid.UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
        extra_where: Sequence[Any] = (),
        stmt: Select[Any] | None = None,
    ) -> Page[ModelT]:
        query = stmt if stmt is not None else self._scoped(project_id)
        for clause in extra_where:
            query = query.where(clause)

        if cursor:
            c_ts, c_id = decode_cursor(cursor)
            query = query.where(
                (self._order_col < c_ts)
                | ((self._order_col == c_ts) & (self.model.id < c_id))  # type: ignore[attr-defined]
            )

        query = query.order_by(self._order_col.desc(), self.model.id.desc())  # type: ignore[attr-defined]
        # Fetch one extra row to learn whether another page exists without a
        # second COUNT query.
        rows = list((await self.session.execute(query.limit(limit + 1))).scalars().all())

        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last = rows[-1]
            next_cursor = encode_cursor(
                getattr(last, self.order_column_name), last.id  # type: ignore[attr-defined]
            )
        return Page(data=rows, next_cursor=next_cursor)

    async def list_all(
        self, *, project_id: uuid.UUID | None = None, extra_where: Sequence[Any] = ()
    ) -> list[ModelT]:
        """Unpaginated read for small, bounded collections only (providers,
        routing policies). Never use on `request`/`gpu_sample`."""
        query = self._scoped(project_id)
        for clause in extra_where:
            query = query.where(clause)
        query = query.order_by(self._order_col.desc())
        return list((await self.session.execute(query)).scalars().all())

    # -- writes -----------------------------------------------------------
    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        await self.session.flush()

    async def delete_by_id(
        self, row_id: uuid.UUID, *, project_id: uuid.UUID | None = None
    ) -> bool:
        instance = await self.get(row_id, project_id=project_id)
        if instance is None:
            return False
        await self.delete(instance)
        return True

    async def delete_where(self, *clauses: Any) -> int:
        result = await self.session.execute(delete(self.model).where(*clauses))
        await self.session.flush()
        return int(result.rowcount or 0)
