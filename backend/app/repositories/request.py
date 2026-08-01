"""Request repository — traffic log reads plus every dashboard/cost aggregate.

All aggregation for the in-app dashboard happens here in Postgres, not via a
Prometheus round-trip (api-contracts.md 3): Prometheus is the source for
Grafana infra panels, Postgres is the source for the in-app widgets, and the
page users load most should not pay an extra network hop.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Select, and_, case, func, select

from app.models.enums import RequestStatus
from app.models.provider import Provider
from app.models.request import Request
from app.repositories.base import BaseRepository

Granularity = Literal["minute", "hour", "day"]

_TRUNC = {"minute": "minute", "hour": "hour", "day": "day"}


class RequestRepository(BaseRepository[Request]):
    model = Request
    order_column_name = "requested_at"

    # -- reads -------------------------------------------------------------
    async def exists_event(self, event_id: str) -> bool:
        stmt = select(Request.id).where(Request.event_id == event_id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    def filtered_stmt(
        self,
        project_id: uuid.UUID,
        *,
        model_id: str | None = None,
        status: RequestStatus | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> Select[Any]:
        stmt = select(Request).where(Request.project_id == project_id)
        if model_id:
            stmt = stmt.where(Request.model_id == model_id)
        if status:
            stmt = stmt.where(Request.status == status)
        if since:
            stmt = stmt.where(Request.requested_at >= since)
        if until:
            stmt = stmt.where(Request.requested_at < until)
        return stmt

    async def get_by_trace_id(
        self, project_id: uuid.UUID, trace_id: str
    ) -> Request | None:
        stmt = select(Request).where(
            Request.project_id == project_id, Request.trace_id == trace_id
        )
        return (await self.session.execute(stmt)).scalars().first()

    # -- aggregates --------------------------------------------------------
    async def summary(
        self, project_id: uuid.UUID, *, since: datetime, until: datetime | None = None
    ) -> dict[str, Any]:
        """KPI roll-up over a window. One query, not one per widget."""
        until = until or datetime.now(timezone.utc)
        stmt = select(
            func.count().label("total"),
            func.coalesce(func.sum(Request.cost_usd), Decimal("0")).label("cost"),
            func.coalesce(func.avg(Request.latency_ms), 0).label("avg_latency"),
            func.coalesce(
                func.sum(Request.input_tokens + Request.output_tokens), 0
            ).label("tokens"),
            func.coalesce(
                func.sum(case((Request.status == RequestStatus.SUCCESS, 1), else_=0)), 0
            ).label("successes"),
        ).where(
            Request.project_id == project_id,
            Request.requested_at >= since,
            Request.requested_at < until,
        )
        row = (await self.session.execute(stmt)).one()
        total = int(row.total)
        successes = int(row.successes)
        window_minutes = max((until - since).total_seconds() / 60.0, 1.0)
        return {
            "request_count": total,
            "cost_usd": float(row.cost),
            "avg_latency_ms": float(row.avg_latency),
            "tokens_used": int(row.tokens),
            "success_rate_pct": round(successes / total * 100, 2) if total else 100.0,
            "error_rate_pct": round((total - successes) / total * 100, 2) if total else 0.0,
            "requests_per_minute": round(total / window_minutes, 2),
        }

    async def usage_by_model(
        self, project_id: uuid.UUID, *, since: datetime, limit: int = 20
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Request.model_id,
                func.count().label("request_count"),
                func.coalesce(func.sum(Request.cost_usd), Decimal("0")).label("cost"),
                func.coalesce(
                    func.sum(Request.input_tokens + Request.output_tokens), 0
                ).label("tokens"),
            )
            .where(Request.project_id == project_id, Request.requested_at >= since)
            .group_by(Request.model_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [
            {
                "model_id": r.model_id,
                "request_count": int(r.request_count),
                "cost_usd": float(r.cost),
                "tokens": int(r.tokens),
            }
            for r in (await self.session.execute(stmt)).all()
        ]

    async def usage_by_provider(
        self, project_id: uuid.UUID, *, since: datetime
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Provider.provider_type,
                func.count().label("request_count"),
                func.coalesce(func.sum(Request.cost_usd), Decimal("0")).label("cost"),
            )
            .join(Provider, Provider.id == Request.provider_id)
            .where(Request.project_id == project_id, Request.requested_at >= since)
            .group_by(Provider.provider_type)
            .order_by(func.count().desc())
        )
        return [
            {
                "provider_type": str(r.provider_type),
                "request_count": int(r.request_count),
                "cost_usd": float(r.cost),
            }
            for r in (await self.session.execute(stmt)).all()
        ]

    async def timeseries(
        self,
        project_id: uuid.UUID,
        *,
        since: datetime,
        until: datetime | None = None,
        granularity: Granularity = "hour",
    ) -> list[dict[str, Any]]:
        until = until or datetime.now(timezone.utc)
        bucket = func.date_trunc(_TRUNC[granularity], Request.requested_at).label("bucket")
        stmt = (
            select(
                bucket,
                func.count().label("request_count"),
                func.coalesce(func.sum(Request.cost_usd), Decimal("0")).label("cost"),
                func.coalesce(func.avg(Request.latency_ms), 0).label("avg_latency"),
                func.coalesce(
                    func.sum(Request.input_tokens + Request.output_tokens), 0
                ).label("tokens"),
                func.coalesce(
                    func.sum(case((Request.status != RequestStatus.SUCCESS, 1), else_=0)),
                    0,
                ).label("errors"),
            )
            .where(
                Request.project_id == project_id,
                Request.requested_at >= since,
                Request.requested_at < until,
            )
            .group_by(bucket)
            .order_by(bucket)
        )
        return [
            {
                "bucket": r.bucket.isoformat(),
                "request_count": int(r.request_count),
                "cost_usd": float(r.cost),
                "avg_latency_ms": float(r.avg_latency),
                "tokens": int(r.tokens),
                "error_count": int(r.errors),
            }
            for r in (await self.session.execute(stmt)).all()
        ]

    async def cost_breakdown(
        self,
        project_id: uuid.UUID,
        *,
        since: datetime,
        until: datetime | None = None,
        dimension: Literal["model", "provider", "day", "tag"] = "model",
    ) -> list[dict[str, Any]]:
        until = until or datetime.now(timezone.utc)
        base_where = and_(
            Request.project_id == project_id,
            Request.requested_at >= since,
            Request.requested_at < until,
        )
        cost = func.coalesce(func.sum(Request.cost_usd), Decimal("0")).label("cost")
        count = func.count().label("request_count")

        if dimension == "model":
            stmt = (
                select(Request.model_id.label("key"), cost, count)
                .where(base_where)
                .group_by(Request.model_id)
            )
        elif dimension == "provider":
            stmt = (
                select(Provider.provider_type.label("key"), cost, count)
                .join(Provider, Provider.id == Request.provider_id)
                .where(base_where)
                .group_by(Provider.provider_type)
            )
        elif dimension == "day":
            day = func.date_trunc("day", Request.requested_at).label("key")
            stmt = select(day, cost, count).where(base_where).group_by(day).order_by(day)
        else:  # tag — one row per distinct origin tag
            tag = func.jsonb_array_elements_text(Request.tags).label("key")
            stmt = select(tag, cost, count).where(base_where).group_by(tag)

        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "key": r.key.isoformat() if hasattr(r.key, "isoformat") else str(r.key),
                "cost_usd": float(r.cost),
                "request_count": int(r.request_count),
            }
            for r in rows
        ]

    async def leaderboard_rows(
        self, project_id: uuid.UUID, *, since: datetime
    ) -> list[dict[str, Any]]:
        """Per-model cost/latency/reliability from real traffic.

        Quality metrics (judge score, hallucination rate) live in
        `EvaluationResult` and are merged on top of this by the leaderboard
        route — this repository stays the owner of `request`-derived facts
        only.
        """
        stmt = (
            select(
                Request.model_id,
                func.count().label("request_count"),
                func.coalesce(func.avg(Request.cost_usd), Decimal("0")).label("avg_cost"),
                func.coalesce(func.avg(Request.latency_ms), 0).label("avg_latency"),
                func.coalesce(
                    func.sum(case((Request.status == RequestStatus.SUCCESS, 1), else_=0)),
                    0,
                ).label("successes"),
            )
            .where(Request.project_id == project_id, Request.requested_at >= since)
            .group_by(Request.model_id)
        )
        out = []
        for r in (await self.session.execute(stmt)).all():
            total = int(r.request_count)
            out.append(
                {
                    "model_id": r.model_id,
                    "request_count": total,
                    "avg_cost_usd": float(r.avg_cost),
                    "avg_latency_ms": float(r.avg_latency),
                    "reliability_pct": round(int(r.successes) / total * 100, 2)
                    if total
                    else 0.0,
                }
            )
        return out

    async def error_reasons(
        self, project_id: uuid.UUID, *, since: datetime, limit: int = 10
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                func.coalesce(Request.error_message, "unknown").label("reason"),
                func.count().label("count"),
            )
            .where(
                Request.project_id == project_id,
                Request.requested_at >= since,
                Request.status != RequestStatus.SUCCESS,
            )
            .group_by("reason")
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [
            {"reason": r.reason, "count": int(r.count)}
            for r in (await self.session.execute(stmt)).all()
        ]

    async def prune_older_than(self, cutoff: datetime) -> int:
        return await self.delete_where(Request.requested_at < cutoff)

    @staticmethod
    def start_of_today() -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def window(days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days)
