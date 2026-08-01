"""Shared Pydantic pieces: ORM base, pagination envelope, problem body."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    """Response models read straight off SQLAlchemy instances."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """Cursor pagination envelope (api-contracts.md 2)."""

    data: list[T]
    next_cursor: str | None = None


class Problem(BaseModel):
    """RFC 7807 body. Declared so it shows up in the generated OpenAPI."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


class Acknowledgement(BaseModel):
    ok: bool = True
    detail: str | None = None
