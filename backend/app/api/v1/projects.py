"""Projects API (T014).

Single-tenant alpha: a caller authenticated for project X can only see and
modify project X. Listing returns that one project rather than every project on
the instance — the auth boundary is the project, not the process (ADR-002).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import AdminDep, AuthDep, SessionDep
from app.core.errors import ConflictProblem, NotFoundProblem, ProblemException
from app.models.tenancy import Project
from app.repositories.tenancy import OrganizationRepository, ProjectRepository
from app.schemas.common import Page
from app.schemas.tenancy import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


def _assert_own_project(auth: AuthDep, project_id: uuid.UUID) -> None:
    if auth.project.id != project_id:
        # 404, not 403: confirming that another project exists is itself
        # information a caller scoped to one project should not receive.
        raise NotFoundProblem("Project", project_id)


@router.get("", response_model=Page[ProjectOut], summary="List projects")
async def list_projects(auth: AuthDep) -> Page[ProjectOut]:
    return Page[ProjectOut](
        data=[ProjectOut.model_validate(auth.project)], next_cursor=None
    )


@router.post(
    "",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
)
async def create_project(
    payload: ProjectCreate, session: SessionDep, auth: AdminDep
) -> ProjectOut:
    projects = ProjectRepository(session)
    if await projects.get_by_slug(payload.slug):
        raise ConflictProblem(f"A project with slug '{payload.slug}' already exists.")

    organization_id = auth.project.organization_id
    if organization_id is None:  # defensive: schema requires it
        organization_id = (
            await OrganizationRepository(session).get_or_create_default()
        ).id

    project = await projects.add(
        Project(
            organization_id=organization_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
    )
    return ProjectOut.model_validate(project)


@router.get("/{project_id}", response_model=ProjectOut, summary="Get project")
async def get_project(project_id: uuid.UUID, auth: AuthDep) -> ProjectOut:
    _assert_own_project(auth, project_id)
    return ProjectOut.model_validate(auth.project)


@router.patch("/{project_id}", response_model=ProjectOut, summary="Update project")
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    session: SessionDep,
    auth: AdminDep,
) -> ProjectOut:
    _assert_own_project(auth, project_id)
    project = auth.project
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    await session.flush()
    return ProjectOut.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
)
async def delete_project(
    project_id: uuid.UUID, session: SessionDep, auth: AdminDep
) -> None:
    _assert_own_project(auth, project_id)
    # Deleting the project you are authenticated as would revoke the caller's
    # own credentials mid-request. Refuse rather than half-perform it.
    raise ProblemException(
        status.HTTP_409_CONFLICT,
        "A project cannot delete itself. Authenticate with a key belonging to "
        "another project to delete this one.",
        type_="https://llmplane.dev/problems/conflict",
    )
