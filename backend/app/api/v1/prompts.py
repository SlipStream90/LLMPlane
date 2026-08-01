"""Prompts API (T022): CRUD, versions, diff, rollback."""

from __future__ import annotations

import difflib
import uuid

from fastapi import APIRouter, status

from app.api.deps import ProjectDep, SessionDep
from app.core.errors import ConflictProblem, NotFoundProblem
from app.models.prompt import Prompt
from app.repositories.prompt import PromptRepository, PromptVersionRepository
from app.schemas.prompt import (
    DiffOp,
    PromptCreate,
    PromptDiffOut,
    PromptOut,
    PromptRollbackRequest,
    PromptUpdate,
    PromptVersionCreate,
    PromptVersionOut,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])


async def _out(session, prompt: Prompt) -> PromptOut:
    latest = await PromptVersionRepository(session).latest_version_number(prompt.id)
    out = PromptOut.model_validate(prompt)
    out.latest_version_number = latest
    return out


@router.get("", response_model=list[PromptOut], summary="List prompts")
async def list_prompts(session: SessionDep, project: ProjectDep) -> list[PromptOut]:
    prompts = await PromptRepository(session).list_all(project_id=project.id)
    return [await _out(session, p) for p in prompts]


@router.post(
    "",
    response_model=PromptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create prompt",
)
async def create_prompt(
    payload: PromptCreate, session: SessionDep, project: ProjectDep
) -> PromptOut:
    repo = PromptRepository(session)
    if await repo.get_by_name(project.id, payload.name):
        raise ConflictProblem(f"A prompt named '{payload.name}' already exists.")

    prompt = await repo.add(
        Prompt(
            project_id=project.id,
            name=payload.name,
            description=payload.description,
        )
    )
    if payload.content:
        await PromptVersionRepository(session).create_version(
            prompt_id=prompt.id,
            content=payload.content,
            system_prompt=payload.system_prompt,
            note="initial version",
        )
    return await _out(session, prompt)


@router.get("/{prompt_id}", response_model=PromptOut, summary="Get prompt")
async def get_prompt(
    prompt_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> PromptOut:
    prompt = await PromptRepository(session).get(prompt_id, project_id=project.id)
    if prompt is None:
        raise NotFoundProblem("Prompt", prompt_id)
    return await _out(session, prompt)


@router.patch("/{prompt_id}", response_model=PromptOut, summary="Update prompt metadata")
async def update_prompt(
    prompt_id: uuid.UUID,
    payload: PromptUpdate,
    session: SessionDep,
    project: ProjectDep,
) -> PromptOut:
    """Metadata only — prompt *content* is versioned and changes only by
    creating a new version."""
    prompt = await PromptRepository(session).get(prompt_id, project_id=project.id)
    if prompt is None:
        raise NotFoundProblem("Prompt", prompt_id)
    if payload.name is not None:
        prompt.name = payload.name
    if payload.description is not None:
        prompt.description = payload.description
    await session.flush()
    return await _out(session, prompt)


@router.delete(
    "/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete prompt"
)
async def delete_prompt(
    prompt_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> None:
    repo = PromptRepository(session)
    prompt = await repo.get(prompt_id, project_id=project.id)
    if prompt is None:
        raise NotFoundProblem("Prompt", prompt_id)
    await repo.delete(prompt)


@router.get(
    "/{prompt_id}/versions",
    response_model=list[PromptVersionOut],
    summary="List versions",
)
async def list_versions(
    prompt_id: uuid.UUID, session: SessionDep, project: ProjectDep
) -> list[PromptVersionOut]:
    await _require_prompt(session, prompt_id, project.id)
    versions = await PromptVersionRepository(session).list_for_prompt(prompt_id)
    return [PromptVersionOut.model_validate(v) for v in versions]


@router.post(
    "/{prompt_id}/versions",
    response_model=PromptVersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new version",
)
async def create_version(
    prompt_id: uuid.UUID,
    payload: PromptVersionCreate,
    session: SessionDep,
    project: ProjectDep,
) -> PromptVersionOut:
    await _require_prompt(session, prompt_id, project.id)
    version = await PromptVersionRepository(session).create_version(
        prompt_id=prompt_id,
        content=payload.content,
        system_prompt=payload.system_prompt,
        note=payload.note,
    )
    return PromptVersionOut.model_validate(version)


@router.get(
    "/{prompt_id}/versions/{a}/diff/{b}",
    response_model=PromptDiffOut,
    summary="Diff two prompt versions",
)
async def diff_versions(
    prompt_id: uuid.UUID,
    a: int,
    b: int,
    session: SessionDep,
    project: ProjectDep,
) -> PromptDiffOut:
    """Line-level opcodes between two versions.

    Computed on read from the two stored contents — there is no diff table
    (data-models.md 2). `difflib` is stdlib and deterministic, which matters
    because the frontend renders these opcodes directly.
    """
    await _require_prompt(session, prompt_id, project.id)
    repo = PromptVersionRepository(session)
    version_a = await repo.get_version(prompt_id, a)
    version_b = await repo.get_version(prompt_id, b)
    if version_a is None:
        raise NotFoundProblem("Prompt version", a)
    if version_b is None:
        raise NotFoundProblem("Prompt version", b)

    left = version_a.content.splitlines(keepends=True)
    right = version_b.content.splitlines(keepends=True)
    ops: list[DiffOp] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, left, right, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            ops.append(DiffOp(op="equal", text="".join(left[i1:i2])))
        elif tag == "delete":
            ops.append(DiffOp(op="delete", text="".join(left[i1:i2])))
        elif tag == "insert":
            ops.append(DiffOp(op="insert", text="".join(right[j1:j2])))
        else:  # replace — emit the incoming text, matching the contract's op set
            ops.append(DiffOp(op="replace", text="".join(right[j1:j2])))

    return PromptDiffOut(from_version=a, to_version=b, diff=ops)


@router.post(
    "/{prompt_id}/rollback/{version_number}",
    response_model=PromptVersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Roll back to an earlier version",
)
async def rollback(
    prompt_id: uuid.UUID,
    version_number: int,
    payload: PromptRollbackRequest,
    session: SessionDep,
    project: ProjectDep,
) -> PromptVersionOut:
    """Rollback appends a *new* version copying the old content.

    History is never rewritten or truncated: "we reverted to v3" is itself a
    fact worth keeping, and a version table that can lose entries is not an
    audit trail.
    """
    await _require_prompt(session, prompt_id, project.id)
    repo = PromptVersionRepository(session)
    source = await repo.get_version(prompt_id, version_number)
    if source is None:
        raise NotFoundProblem("Prompt version", version_number)

    latest = await repo.latest_version_number(prompt_id)
    if version_number == latest:
        raise ConflictProblem(
            f"Version {version_number} is already the latest version."
        )

    version = await repo.create_version(
        prompt_id=prompt_id,
        content=source.content,
        system_prompt=source.system_prompt,
        note=payload.note or f"rollback to v{version_number}",
    )
    return PromptVersionOut.model_validate(version)


async def _require_prompt(session, prompt_id: uuid.UUID, project_id: uuid.UUID) -> None:
    if await PromptRepository(session).get(prompt_id, project_id=project_id) is None:
        raise NotFoundProblem("Prompt", prompt_id)
