"""Routing policies API (T017): CRUD + activate."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import ProjectDep, SessionDep
from app.core.errors import ConflictProblem, NotFoundProblem
from app.core.redis import publish_event
from app.models.routing import RoutingPolicy
from app.repositories.routing import RoutingPolicyRepository
from app.schemas.routing import (
    RoutingPolicyActivated,
    RoutingPolicyCreate,
    RoutingPolicyOut,
    RoutingPolicyUpdate,
)
from app.services.routing_config_service import RoutingConfigError, RoutingConfigService

router = APIRouter(prefix="/routing-policies", tags=["routing-policies"])


@router.get("", response_model=list[RoutingPolicyOut], summary="List routing policies")
async def list_policies(
    session: SessionDep, project: ProjectDep
) -> list[RoutingPolicyOut]:
    policies = await RoutingPolicyRepository(session).list_for_project(project.id)
    return [RoutingPolicyOut.model_validate(p) for p in policies]


@router.post(
    "",
    response_model=RoutingPolicyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create routing policy",
)
async def create_policy(
    payload: RoutingPolicyCreate, session: SessionDep, project: ProjectDep
) -> RoutingPolicyOut:
    repo = RoutingPolicyRepository(session)
    if any(p.name == payload.name for p in await repo.list_for_project(project.id)):
        raise ConflictProblem(
            f"A routing policy named '{payload.name}' already exists."
        )

    # Validate the allowlist against the real catalog at write time. Creating a
    # policy that cannot be rendered would just move the failure to activation,
    # when the user is expecting traffic to shift.
    service = RoutingConfigService(session)
    try:
        await service.resolve_models(project.id, payload.model_allowlist)
    except RoutingConfigError as exc:
        raise ConflictProblem(str(exc)) from exc

    policy = await repo.add(
        RoutingPolicy(
            project_id=project.id,
            name=payload.name,
            strategy=payload.strategy,
            config=payload.config,
            model_allowlist=payload.model_allowlist,
            is_active=False,
        )
    )
    return RoutingPolicyOut.model_validate(policy)


@router.get("/active", response_model=RoutingPolicyOut, summary="Get the active policy")
async def get_active_policy(
    session: SessionDep, project: ProjectDep
) -> RoutingPolicyOut:
    policy = await RoutingPolicyRepository(session).get_active(project.id)
    if policy is None:
        raise NotFoundProblem("Active routing policy", project.id)
    return RoutingPolicyOut.model_validate(policy)


@router.get("/{policy_id}", response_model=RoutingPolicyOut, summary="Get policy")
async def get_policy(
    policy_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> RoutingPolicyOut:
    policy = await RoutingPolicyRepository(session).get(
        policy_id, project_id=project.id
    )
    if policy is None:
        raise NotFoundProblem("Routing policy", policy_id)
    return RoutingPolicyOut.model_validate(policy)


@router.patch("/{policy_id}", response_model=RoutingPolicyOut, summary="Update policy")
async def update_policy(
    policy_id: uuid.UUID,
    payload: RoutingPolicyUpdate,
    session: SessionDep,
    project: ProjectDep,
) -> RoutingPolicyOut:
    repo = RoutingPolicyRepository(session)
    policy = await repo.get(policy_id, project_id=project.id)
    if policy is None:
        raise NotFoundProblem("Routing policy", policy_id)

    if payload.name is not None:
        policy.name = payload.name
    if payload.config is not None:
        policy.config = payload.config
    if payload.model_allowlist is not None:
        policy.model_allowlist = payload.model_allowlist
    await session.flush()

    # An edit to the live policy must reach the gateway, or the UI would show
    # a policy that traffic is not actually following.
    if policy.is_active:
        service = RoutingConfigService(session)
        try:
            await service.apply_policy(policy)
        except RoutingConfigError as exc:
            raise ConflictProblem(str(exc)) from exc

    return RoutingPolicyOut.model_validate(policy)


@router.post(
    "/{policy_id}/activate",
    response_model=RoutingPolicyActivated,
    summary="Activate policy and push config to the gateway",
)
async def activate_policy(
    policy_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> RoutingPolicyActivated:
    """Deactivate any other active policy, activate this one, push to gateway.

    Returns 409 when the policy references a model that is not registered under
    any provider (api-contracts.md 3). A gateway that is merely unreachable is
    *not* a 409: the config file is written and the response says `deferred`,
    because the policy change is real and will take effect on gateway restart —
    reporting that honestly beats either lying about success or refusing a
    valid change (Article V).
    """
    repo = RoutingPolicyRepository(session)
    policy = await repo.get(policy_id, project_id=project.id)
    if policy is None:
        raise NotFoundProblem("Routing policy", policy_id)

    service = RoutingConfigService(session)
    try:
        models = await service.resolve_models(project.id, policy.model_allowlist)
    except RoutingConfigError as exc:
        raise ConflictProblem(str(exc)) from exc

    await repo.activate(policy)
    document = service.render(policy, models)
    push = await service.push(document, models)

    await publish_event(
        "routing",
        "policy_activated",
        {
            "policy_id": str(policy.id),
            "name": policy.name,
            "strategy": str(policy.strategy),
            "gateway_config_status": push.status,
        },
    )

    return RoutingPolicyActivated(
        **RoutingPolicyOut.model_validate(policy).model_dump(),
        gateway_config_status=push.status,
        gateway_detail=push.detail,
    )


@router.delete(
    "/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete policy",
)
async def delete_policy(
    policy_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> None:
    repo = RoutingPolicyRepository(session)
    policy = await repo.get(policy_id, project_id=project.id)
    if policy is None:
        raise NotFoundProblem("Routing policy", policy_id)
    if policy.is_active:
        raise ConflictProblem(
            "The active routing policy cannot be deleted. Activate another "
            "policy first."
        )
    await repo.delete(policy)
