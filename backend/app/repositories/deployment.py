"""Deployment and GpuSample repositories."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models.deployment import Deployment, GpuSample
from app.models.enums import DeploymentStatus
from app.repositories.base import BaseRepository


class DeploymentRepository(BaseRepository[Deployment]):
    model = Deployment

    async def list_for_project(self, project_id: uuid.UUID) -> list[Deployment]:
        return await self.list_all(project_id=project_id)

    async def count_active(self, project_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(
            Deployment.project_id == project_id,
            Deployment.status == DeploymentStatus.RUNNING,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def get_by_container_id(self, container_id: str) -> Deployment | None:
        stmt = select(Deployment).where(Deployment.container_id == container_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def used_ports(self) -> set[int]:
        stmt = select(Deployment.port).where(Deployment.port.is_not(None))
        return {int(p) for p in (await self.session.execute(stmt)).scalars().all()}


class GpuSampleRepository(BaseRepository[GpuSample]):
    model = GpuSample
    order_column_name = "sampled_at"

    async def recent_for_deployment(
        self, deployment_id: uuid.UUID, *, minutes: int = 60, limit: int = 500
    ) -> list[GpuSample]:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        stmt = (
            select(GpuSample)
            .where(
                GpuSample.deployment_id == deployment_id,
                GpuSample.sampled_at >= since,
            )
            .order_by(GpuSample.sampled_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest_host_samples(self, *, within_minutes: int = 5) -> list[GpuSample]:
        """Most recent sample per GPU index across the host, for the dashboard
        gauge widgets."""
        since = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        subq = (
            select(
                GpuSample.gpu_index,
                func.max(GpuSample.sampled_at).label("latest"),
            )
            .where(GpuSample.sampled_at >= since)
            .group_by(GpuSample.gpu_index)
            .subquery()
        )
        stmt = select(GpuSample).join(
            subq,
            (GpuSample.gpu_index == subq.c.gpu_index)
            & (GpuSample.sampled_at == subq.c.latest),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def avg_gpu_util(self, *, within_minutes: int = 5) -> float | None:
        since = datetime.now(timezone.utc) - timedelta(minutes=within_minutes)
        stmt = select(func.avg(GpuSample.gpu_util_pct)).where(
            GpuSample.sampled_at >= since
        )
        value = (await self.session.execute(stmt)).scalar_one_or_none()
        return float(value) if value is not None else None

    async def prune_older_than(self, cutoff: datetime) -> int:
        return await self.delete_where(GpuSample.sampled_at < cutoff)
