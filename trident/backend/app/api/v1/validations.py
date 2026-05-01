"""Validation run API — /projects/{project_id}/directives/{directive_id}/validations/* (VALIDATION_001)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.db.session import get_db
from app.models.enums import ProjectMemberRole
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.schemas.validation_schemas import (
    ValidationRunCompleteRequest,
    ValidationRunCreateRequest,
    ValidationRunDetail,
    ValidationRunListResponse,
    ValidationRunWaiveRequest,
)
from app.services.validation_run_service import (
    ValidationDirectiveMismatchError,
    ValidationInvalidTransitionError,
    ValidationNotFoundError,
    ValidationPatchMismatchError,
    ValidationRunService,
    ValidationTerminalError,
)

router = APIRouter()


def _require_role(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, minimum: ProjectMemberRole) -> None:
    try:
        MembershipRepository(db).require_role_at_least(user_id, project_id, minimum)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


def _svc_err(e: Exception) -> HTTPException:
    if isinstance(e, ValidationNotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, (ValidationDirectiveMismatchError, ValidationPatchMismatchError)):
        return HTTPException(status_code=422, detail=str(e))
    if isinstance(e, ValidationTerminalError):
        return HTTPException(status_code=409, detail=str(e))
    if isinstance(e, ValidationInvalidTransitionError):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=400, detail=str(e))


# ── POST / ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ValidationRunDetail, status_code=201)
def create_validation(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    body: ValidationRunCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ValidationRunDetail:
    _require_role(db, user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    try:
        return ValidationRunService(db).create(project_id, directive_id, user.id, body)
    except Exception as e:
        raise _svc_err(e) from None


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get("/", response_model=ValidationRunListResponse)
def list_validations(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ValidationRunListResponse:
    _require_role(db, user.id, project_id, ProjectMemberRole.VIEWER)
    try:
        return ValidationRunService(db).list_for_directive(project_id, directive_id)
    except Exception as e:
        raise _svc_err(e) from None


# ── GET /{validation_id} ──────────────────────────────────────────────────────

@router.get("/{validation_id}", response_model=ValidationRunDetail)
def get_validation(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    validation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ValidationRunDetail:
    _require_role(db, user.id, project_id, ProjectMemberRole.VIEWER)
    try:
        return ValidationRunService(db).get(project_id, directive_id, validation_id)
    except Exception as e:
        raise _svc_err(e) from None


# ── POST /{validation_id}/start ───────────────────────────────────────────────

@router.post("/{validation_id}/start", response_model=ValidationRunDetail)
def start_validation(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    validation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ValidationRunDetail:
    _require_role(db, user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    try:
        return ValidationRunService(db).start(project_id, directive_id, validation_id, user.id)
    except Exception as e:
        raise _svc_err(e) from None


# ── POST /{validation_id}/complete ────────────────────────────────────────────

@router.post("/{validation_id}/complete", response_model=ValidationRunDetail)
def complete_validation(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    validation_id: uuid.UUID,
    body: ValidationRunCompleteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ValidationRunDetail:
    _require_role(db, user.id, project_id, ProjectMemberRole.ADMIN)
    try:
        return ValidationRunService(db).complete(project_id, directive_id, validation_id, user.id, body)
    except Exception as e:
        raise _svc_err(e) from None


# ── POST /{validation_id}/waive ───────────────────────────────────────────────

@router.post("/{validation_id}/waive", response_model=ValidationRunDetail)
def waive_validation(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    validation_id: uuid.UUID,
    body: ValidationRunWaiveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ValidationRunDetail:
    _require_role(db, user.id, project_id, ProjectMemberRole.ADMIN)
    try:
        return ValidationRunService(db).waive(project_id, directive_id, validation_id, user.id, body)
    except Exception as e:
        raise _svc_err(e) from None
