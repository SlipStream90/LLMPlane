"""API v1 router assembly.

Auth is applied at the router level, once, rather than repeated on every route:
`/api/v1/*` requires a project API key except `auth` (bootstrap, which cannot
have one yet). Routes that additionally need the `admin` scope declare it
themselves via `AdminDep`.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_auth_context
from app.api.v1 import (
    api_keys,
    auth,
    benchmark_datasets,
    benchmarks,
    cost_analytics,
    dashboard,
    deployments,
    evaluations,
    experiments,
    leaderboard,
    playground,
    projects,
    prompts,
    providers,
    routing_policies,
    traces,
)

api_router = APIRouter()

# Unauthenticated by API key (bootstrap-token protected instead).
api_router.include_router(auth.router)

_authenticated = APIRouter(dependencies=[Depends(get_auth_context)])
for module in (
    projects,
    api_keys,
    providers,
    deployments,
    routing_policies,
    playground,
    prompts,
    experiments,
    benchmark_datasets,
    benchmarks,
    evaluations,
    leaderboard,
    dashboard,
    cost_analytics,
    traces,
):
    _authenticated.include_router(module.router)

api_router.include_router(_authenticated)

__all__ = ["api_router"]
