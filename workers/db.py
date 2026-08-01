"""Database access for Celery tasks.

Tasks are synchronous callables but the data layer is async (SQLAlchemy 2.0 +
asyncpg), shared with the backend rather than duplicated (ARCHITECTURE.md 3.2).
`run_async` bridges the two: each task body runs on its own event loop with its
own engine, which avoids the classic failure of an asyncpg pool outliving the
loop it was created on inside a forked worker process.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

T = TypeVar("T")


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """One engine, one session, one transaction, torn down with the loop.

    `NullPool` semantics are approximated by disposing the engine at the end:
    a task is short-lived and pooling across tasks is what breaks under fork.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    finally:
        await engine.dispose()


def run_async(coro_factory: Callable[[], Awaitable[T]]) -> T:
    """Run one coroutine to completion on a fresh event loop."""
    return asyncio.run(coro_factory())
