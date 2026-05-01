"""Governed patch proposal API (PATCH_001).

Mounted at: /projects/{project_id}/directives/{directive_id}/patches
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.db.session import get_db
from app.models.enums import ProjectMemberRole
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.api.deps.git_deps import get_git_provider
from app.git_provider.base import GitProvider
from app.schemas.proposal_schemas import (
    PatchExecuteResponse,
    PatchProposalAcceptResponse,
    PatchProposalCreateRequest,
    PatchProposalDetail,
    PatchProposalListResponse,
    PatchProposalRejectRequest,
    PatchProposalRejectResponse,
)
from app.services.git_project_service import GitNotLinkedError
from app.services.patch_proposal_service import (
    DirectiveMismatchError,
    PatchAlreadyAcceptedError,
    PatchAlreadyExecutedError,
    PatchFileConversionError,
    PatchImmutableError,
    PatchNotExecutableError,
    PatchNotFoundError,
    PatchProposalService,
)

router = APIRouter()


def _require_role(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, minimum: ProjectMemberRole) -> None:
    try:
        MembershipRepository(db).require_role_at_least(user_id, project_id, minimum)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


def _svc_errors(e: Exception) -> HTTPException:
    if isinstance(e, (PatchNotFoundError, DirectiveMismatchError)):
        code = str(e)
        status = 404 if isinstance(e, PatchNotFoundError) else 422
        return HTTPException(status_code=status, detail=code)
    if isinstance(e, PatchImmutableError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, PatchAlreadyAcceptedError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, PatchAlreadyExecutedError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, PatchNotExecutableError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, PatchFileConversionError):
        return HTTPException(status_code=422, detail=str(e))
    if isinstance(e, GitNotLinkedError):
        code = str(e)
        status = 409 if code == "directive_branch_missing" else 404
        return HTTPException(status_code=status, detail=code)
    if isinstance(e, ValueError) and str(e) == "directive_closed":
        return HTTPException(status_code=409, detail="directive_closed")
    return HTTPException(status_code=400, detail=str(e))


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=PatchProposalDetail, status_code=201)
def create_patch(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    body: PatchProposalCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PatchProposalDetail:
    _require_role(db, user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    try:
        return PatchProposalService(db).create(project_id, directive_id, user.id, body)
    except DirectiveMismatchError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    except Exception as e:
        raise _svc_errors(e) from None


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get("/", response_model=PatchProposalListResponse)
def list_patches(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PatchProposalListResponse:
    _require_role(db, user.id, project_id, ProjectMemberRole.VIEWER)
    try:
        return PatchProposalService(db).list_for_directive(project_id, directive_id)
    except DirectiveMismatchError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


# ── GET /{patch_id} ───────────────────────────────────────────────────────────

@router.get("/{patch_id}", response_model=PatchProposalDetail)
def get_patch(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    patch_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PatchProposalDetail:
    _require_role(db, user.id, project_id, ProjectMemberRole.VIEWER)
    try:
        return PatchProposalService(db).get(project_id, directive_id, patch_id)
    except Exception as e:
        raise _svc_errors(e) from None


# ── POST /{patch_id}/accept ───────────────────────────────────────────────────

@router.post("/{patch_id}/accept", response_model=PatchProposalAcceptResponse)
def accept_patch(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    patch_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PatchProposalAcceptResponse:
    _require_role(db, user.id, project_id, ProjectMemberRole.ADMIN)
    try:
        return PatchProposalService(db).accept(project_id, directive_id, patch_id, user.id)
    except Exception as e:
        raise _svc_errors(e) from None


# ── POST /{patch_id}/execute ──────────────────────────────────────────────────

@router.post("/{patch_id}/execute", response_model=PatchExecuteResponse, status_code=201)
def execute_patch(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    patch_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    provider: GitProvider = Depends(get_git_provider),
) -> PatchExecuteResponse:
    _require_role(db, user.id, project_id, ProjectMemberRole.ADMIN)
    try:
        return PatchProposalService(db, provider=provider).execute(
            project_id, directive_id, patch_id, user.id
        )
    except Exception as e:
        raise _svc_errors(e) from None


# ── POST /{patch_id}/reject ───────────────────────────────────────────────────

@router.post("/{patch_id}/reject", response_model=PatchProposalRejectResponse)
def reject_patch(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    patch_id: uuid.UUID,
    body: PatchProposalRejectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PatchProposalRejectResponse:
    _require_role(db, user.id, project_id, ProjectMemberRole.ADMIN)
    try:
        return PatchProposalService(db).reject(project_id, directive_id, patch_id, user.id, body)
    except Exception as e:
        raise _svc_errors(e) from None
