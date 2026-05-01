"""Directive state aggregate endpoints — STATUS_001."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.db.session import get_db
from app.models.enums import ProjectMemberRole
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.schemas.directive_state import DirectiveStateResponse
from app.schemas.execution_state_schemas import ExecutionStateResponse
from app.services.directive_state_service import (
    DirectiveNotFoundError,
    DirectiveProjectMismatchError,
    DirectiveStateService,
)
from app.services.execution_state_service import (
    ExecutionStateMismatchError,
    ExecutionStateNotFoundError,
    ExecutionStateService,
)
from app.services.system_guardrail_service import SystemGuardrailService

router = APIRouter()


def _require_viewer(db: Session, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
    try:
        MembershipRepository(db).require_role_at_least(user_id, project_id, ProjectMemberRole.VIEWER)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.get("/status", response_model=DirectiveStateResponse)
def get_directive_state(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DirectiveStateResponse:
    """Summary state with lifecycle phase and allowed actions (simple). VIEWER+."""
    _require_viewer(db, user.id, project_id)
    try:
        return DirectiveStateService(db).get_state(directive_id, project_id, user.id)
    except DirectiveNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except DirectiveProjectMismatchError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/guardrails")
def get_guardrails(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Diagnostic invariant check — ADMIN+ only. Read-only. No mutations."""
    try:
        MembershipRepository(db).require_role_at_least(user.id, project_id, ProjectMemberRole.ADMIN)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    result = SystemGuardrailService(db).check_directive(directive_id, project_id)
    return {
        "status": result.status,
        "directive_id": str(result.directive_id),
        "project_id": str(result.project_id),
        "checked_at": result.checked_at.isoformat(),
        "violation_count": len(result.violations),
        "violations": [v.as_dict() for v in result.violations],
    }


@router.get("/execution-state", response_model=ExecutionStateResponse)
def get_execution_state(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExecutionStateResponse:
    """Full execution state aggregate — workbench source of truth. VIEWER+.

    DB-derived only. No provider calls. No mutations.
    All fields are computed from: directives, git_repo_links, git_branch_log,
    patch_proposals, validation_runs, proof_objects.
    """
    _require_viewer(db, user.id, project_id)
    try:
        return ExecutionStateService(db).get_execution_state(directive_id, project_id, user.id)
    except ExecutionStateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except ExecutionStateMismatchError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
