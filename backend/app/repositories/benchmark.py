"""Benchmark dataset / run / run-item repositories."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.models.benchmark import BenchmarkDataset, BenchmarkRun, BenchmarkRunItem
from app.models.enums import ItemStatus, RunStatus
from app.repositories.base import BaseRepository


class BenchmarkDatasetRepository(BaseRepository[BenchmarkDataset]):
    model = BenchmarkDataset

    async def list_for_project(self, project_id: uuid.UUID) -> list[BenchmarkDataset]:
        return await self.list_all(project_id=project_id)

    async def get_by_name(
        self, project_id: uuid.UUID, name: str
    ) -> BenchmarkDataset | None:
        stmt = select(BenchmarkDataset).where(
            BenchmarkDataset.project_id == project_id, BenchmarkDataset.name == name
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class BenchmarkRunRepository(BaseRepository[BenchmarkRun]):
    model = BenchmarkRun

    async def list_for_project(self, project_id: uuid.UUID) -> list[BenchmarkRun]:
        return await self.list_all(project_id=project_id)

    async def mark_running(self, run: BenchmarkRun) -> BenchmarkRun:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        await self.session.flush()
        return run

    async def mark_complete(
        self, run: BenchmarkRun, *, failed: bool = False, error: str | None = None
    ) -> BenchmarkRun:
        run.status = RunStatus.FAILED if failed else RunStatus.COMPLETE
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = error
        await self.session.flush()
        return run

    async def refresh_progress(self, run_id: uuid.UUID) -> tuple[int, int]:
        """Recount completed items from the items table and persist it.

        Deliberately a recount rather than an increment: the chord's header
        tasks complete concurrently, and a read-modify-write counter would lose
        updates under that exact concurrency.
        """
        total = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        BenchmarkRunItem.benchmark_run_id == run_id
                    )
                )
            ).scalar_one()
        )
        done = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        BenchmarkRunItem.benchmark_run_id == run_id,
                        BenchmarkRunItem.status.in_(
                            (ItemStatus.COMPLETE, ItemStatus.FAILED)
                        ),
                    )
                )
            ).scalar_one()
        )
        await self.session.execute(
            update(BenchmarkRun)
            .where(BenchmarkRun.id == run_id)
            .values(completed_items=done, total_items=total)
        )
        await self.session.flush()
        return done, total


class BenchmarkRunItemRepository(BaseRepository[BenchmarkRunItem]):
    model = BenchmarkRunItem

    async def bulk_add(self, items: list[BenchmarkRunItem]) -> list[BenchmarkRunItem]:
        self.session.add_all(items)
        await self.session.flush()
        return items

    async def list_for_run(self, run_id: uuid.UUID) -> list[BenchmarkRunItem]:
        stmt = (
            select(BenchmarkRunItem)
            .where(BenchmarkRunItem.benchmark_run_id == run_id)
            .order_by(BenchmarkRunItem.dataset_row_index)
        )
        return list((await self.session.execute(stmt)).scalars().all())
