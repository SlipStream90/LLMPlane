"""Traces API (T033).

List view reads the `Request` table we own. Detail view proxies Langfuse for
span-level data, because Postgres deliberately does not store span detail
(ADR-004).

Langfuse being unconfigured or unreachable is a *degraded*, not failed,
response: the request row is still returned with `langfuse_available: false`
and a reason (Article XIV). A trace list that 500s because a side-car
observability stack is down would be a worse product than one that says so.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Query

from app.api.deps import PaginationDep, ProjectDep, SessionDep, SettingsDep
from app.models.enums import RequestStatus
from app.repositories.request import RequestRepository
from app.schemas.analytics import TraceDetail, TraceOut
from app.schemas.common import Page

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", response_model=Page[TraceOut], summary="List recent request traces")
async def list_traces(
    session: SessionDep,
    project: ProjectDep,
    pagination: PaginationDep,
    model_id: str | None = Query(None),
    status: RequestStatus | None = Query(None),
    since: datetime | None = Query(None),
) -> Page[TraceOut]:
    repo = RequestRepository(session)
    page = await repo.list_page(
        stmt=repo.filtered_stmt(
            project.id, model_id=model_id, status=status, since=since
        ),
        cursor=pagination.cursor,
        limit=pagination.limit,
    )
    return Page[TraceOut](
        data=[TraceOut.model_validate(r) for r in page.data],
        next_cursor=page.next_cursor,
    )


@router.get(
    "/{trace_id}",
    response_model=TraceDetail,
    summary="Full trace detail (proxies Langfuse for span-level data)",
)
async def get_trace(
    trace_id: str,
    session: SessionDep,
    project: ProjectDep,
    settings: SettingsDep,
) -> TraceDetail:
    request_row = await RequestRepository(session).get_by_trace_id(project.id, trace_id)
    request_out = TraceOut.model_validate(request_row) if request_row else None

    if not (
        settings.langfuse_host
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    ):
        return TraceDetail(
            request=request_out,
            langfuse_available=False,
            detail_error=(
                "Langfuse is not configured (LANGFUSE_HOST / LANGFUSE_PUBLIC_KEY / "
                "LANGFUSE_SECRET_KEY). Span-level detail is unavailable; the "
                "request record is returned from the control-plane database."
            ),
        )

    # Langfuse v3 public API uses HTTP Basic with public/secret key
    # (ARCHITECTURE.md 2 pins v3, not the v4 pre-release).
    token = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode("utf-8")
    ).decode("ascii")

    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            response = await http.get(
                f"{settings.langfuse_host.rstrip('/')}/api/public/traces/{trace_id}",
                headers={"Authorization": f"Basic {token}"},
            )
        if response.status_code == 404:
            return TraceDetail(
                request=request_out,
                langfuse_available=True,
                detail_error=f"Langfuse has no trace with id '{trace_id}'.",
            )
        response.raise_for_status()
        return TraceDetail(
            request=request_out, langfuse_available=True, trace=response.json()
        )
    except httpx.HTTPError as exc:
        logger.warning("Langfuse trace fetch failed for %s: %s", trace_id, exc)
        return TraceDetail(
            request=request_out,
            langfuse_available=False,
            detail_error=f"Langfuse is unreachable: {exc}",
        )
