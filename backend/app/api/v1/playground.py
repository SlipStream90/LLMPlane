"""Side-by-side playground (T027).

One prompt, N models, fanned out concurrently with `asyncio.gather` against the
gateway — not Celery. This is a synchronous user-facing request, not a
background job (api-contracts.md 3).

Partial failure is a first-class outcome: one model timing out returns an item
with `error` set while every other model's response is still delivered
(Article XIV).
"""

from __future__ import annotations

import asyncio
import uuid

import httpx
from fastapi import APIRouter, status

from app.api.deps import ProjectDep, SessionDep
from app.core.config import get_settings
from app.core.errors import NotFoundProblem, ValidationProblem
from app.models.playground import PlaygroundComparison, PlaygroundResponse
from app.repositories.playground import (
    PlaygroundComparisonRepository,
    PlaygroundResponseRepository,
)
from app.repositories.provider import ProviderModelRepository
from app.schemas.playground import (
    PlaygroundCompareRequest,
    PlaygroundCompareResponse,
    PlaygroundComparisonOut,
    PlaygroundResponseItem,
    PlaygroundVoteRequest,
)
from app.services.gateway_client import CompletionResult, GatewayClient, estimate_cost

router = APIRouter(prefix="/playground", tags=["playground"])


@router.post(
    "/compare",
    response_model=PlaygroundCompareResponse,
    summary="Run one prompt against N models concurrently",
)
async def compare(
    payload: PlaygroundCompareRequest, session: SessionDep, project: ProjectDep
) -> PlaygroundCompareResponse:
    settings = get_settings()
    if len(payload.model_ids) > settings.playground_max_models:
        raise ValidationProblem(
            f"At most {settings.playground_max_models} models can be compared at "
            f"once; {len(payload.model_ids)} were requested."
        )

    catalog_repo = ProviderModelRepository(session)
    catalog = {}
    for model_id in payload.model_ids:
        catalog[model_id] = await catalog_repo.get_by_model_id(project.id, model_id)

    unknown = [m for m, row in catalog.items() if row is None]
    if unknown:
        raise ValidationProblem(
            "These model ids are not registered under any provider in this "
            f"project: {', '.join(sorted(unknown))}",
            {"unknown_model_ids": sorted(unknown)},
        )

    comparison = await PlaygroundComparisonRepository(session).add(
        PlaygroundComparison(
            project_id=project.id,
            prompt_text=payload.prompt,
            system_prompt=payload.system_prompt,
            temperature=payload.temperature,
        )
    )

    gateway = GatewayClient()
    # One shared connection pool across the fan-out; N models means N
    # concurrent requests, not N clients.
    async with httpx.AsyncClient(
        timeout=settings.playground_per_model_timeout_s
    ) as http:
        results: list[CompletionResult] = list(
            await asyncio.gather(
                *(
                    gateway.chat_completion(
                        model_id=model_id,
                        prompt=payload.prompt,
                        system_prompt=payload.system_prompt,
                        temperature=payload.temperature,
                        max_tokens=payload.max_tokens,
                        project_id=project.id,
                        origin="playground",
                        timeout_s=settings.playground_per_model_timeout_s,
                        client=http,
                    )
                    for model_id in payload.model_ids
                )
            )
        )

    rows: list[PlaygroundResponse] = []
    items: list[PlaygroundResponseItem] = []
    for result in results:
        model = catalog[result.model_id]
        cost = result.cost_usd
        if cost is None and result.ok and model is not None:
            cost = estimate_cost(
                result.input_tokens,
                result.output_tokens,
                model.input_price_per_1m,
                model.output_price_per_1m,
            )

        rows.append(
            PlaygroundResponse(
                comparison_id=comparison.id,
                provider_model_id=model.id if model else None,
                model_id=result.model_id,
                response_text=result.response_text,
                error=result.error,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=cost,
            )
        )

    stored = await PlaygroundResponseRepository(session).bulk_add(rows)
    for row in stored:
        items.append(
            PlaygroundResponseItem(
                provider_model_id=row.provider_model_id,
                model_id=row.model_id,
                response_text=row.response_text,
                error=row.error,
                cost_usd=float(row.cost_usd) if row.cost_usd is not None else None,
                latency_ms=row.latency_ms,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                judge_score=row.judge_score,
            )
        )

    return PlaygroundCompareResponse(comparison_id=comparison.id, responses=items)


@router.get(
    "/comparisons/{comparison_id}",
    response_model=PlaygroundCompareResponse,
    summary="Fetch a stored comparison",
)
async def get_comparison(
    comparison_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> PlaygroundCompareResponse:
    comparison = await PlaygroundComparisonRepository(session).get_with_responses(
        comparison_id, project.id
    )
    if comparison is None:
        raise NotFoundProblem("Playground comparison", comparison_id)
    return PlaygroundCompareResponse(
        comparison_id=comparison.id,
        responses=[
            PlaygroundResponseItem(
                provider_model_id=r.provider_model_id,
                model_id=r.model_id,
                response_text=r.response_text,
                error=r.error,
                cost_usd=float(r.cost_usd) if r.cost_usd is not None else None,
                latency_ms=r.latency_ms,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                judge_score=r.judge_score,
            )
            for r in comparison.responses
        ],
    )


@router.get(
    "/comparisons",
    response_model=list[PlaygroundComparisonOut],
    summary="List recent comparisons",
)
async def list_comparisons(
    session: SessionDep, project: ProjectDep
) -> list[PlaygroundComparisonOut]:
    rows = await PlaygroundComparisonRepository(session).list_all(project_id=project.id)
    return [PlaygroundComparisonOut.model_validate(r) for r in rows]


@router.post(
    "/vote",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Record a manual winner vote (PRD 5)",
)
async def vote(
    payload: PlaygroundVoteRequest, session: SessionDep, project: ProjectDep
) -> None:
    repo = PlaygroundResponseRepository(session)
    response = await repo.get_for_project(payload.response_id, project.id)
    if response is None:
        raise NotFoundProblem("Playground response", payload.response_id)
    response.user_vote = payload.vote
    await session.flush()
