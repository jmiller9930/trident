"""Onboarding API — /projects/{project_id}/onboarding/* (ONBOARD_002)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.db.session import get_db
from app.models.enums import AuditActorType, AuditEventType, ProjectMemberRole
from app.models.project import Project
from app.models.project_onboarding import ProjectOnboarding
from app.models.state_enums import OnboardingStatus
from app.models.user import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.membership_repository import MembershipRepository
from app.schemas.onboarding_schemas import (
    OnboardingBeginRequest,
    OnboardingBeginResponse,
    OnboardingScanResponse,
    OnboardingStatusResponse,
)
from app.services.onboarding_scan_service import OnboardingScanService

router = APIRouter()

_IMMUTABLE_STATUSES = {OnboardingStatus.APPROVED.value}
_TERMINAL_STATUSES = {OnboardingStatus.APPROVED.value, OnboardingStatus.REJECTED.value}


def _require_member(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, minimum: ProjectMemberRole) -> None:
    mrepo = MembershipRepository(db)
    try:
        mrepo.require_role_at_least(user_id, project_id, minimum)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


def _get_project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return proj


def _latest_onboarding(db: Session, project_id: uuid.UUID) -> ProjectOnboarding | None:
    return db.scalars(
        select(ProjectOnboarding)
        .where(ProjectOnboarding.project_id == project_id)
        .order_by(ProjectOnboarding.created_at.desc())
        .limit(1)
    ).first()


def _get_active_onboarding_or_404(db: Session, project_id: uuid.UUID) -> ProjectOnboarding:
    row = _latest_onboarding(db, project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="onboarding_not_found")
    return row


def _onboarding_begin_response(row: ProjectOnboarding) -> OnboardingBeginResponse:
    return OnboardingBeginResponse(
        onboarding_id=row.id,
        project_id=row.project_id,
        status=row.status,
        repo_local_path=row.repo_local_path,
        git_commit_sha=row.git_commit_sha,
        created_at=row.created_at,
    )


def _onboarding_status_response(row: ProjectOnboarding) -> OnboardingStatusResponse:
    return OnboardingStatusResponse(
        onboarding_id=row.id,
        project_id=row.project_id,
        status=row.status,
        repo_local_path=row.repo_local_path,
        git_remote_url=row.git_remote_url,
        git_branch=row.git_branch,
        git_commit_sha=row.git_commit_sha,
        language_primary=row.language_primary,
        index_job_id=row.index_job_id,
        approved_by_user_id=row.approved_by_user_id,
        approved_at=row.approved_at,
        rejection_reason=row.rejection_reason,
        previous_onboarding_id=row.previous_onboarding_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ── POST /begin ───────────────────────────────────────────────────────────────

@router.post("/begin", response_model=OnboardingBeginResponse, status_code=201)
def begin_onboarding(
    project_id: uuid.UUID,
    body: OnboardingBeginRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OnboardingBeginResponse:
    _require_member(db, user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    _get_project_or_404(db, project_id)

    existing = _latest_onboarding(db, project_id)
    previous_id: uuid.UUID | None = None
    if existing is not None:
        if existing.status not in _TERMINAL_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"onboarding_already_active_status={existing.status}",
            )
        previous_id = existing.id if existing.status == OnboardingStatus.APPROVED.value else None

    row = ProjectOnboarding(
        project_id=project_id,
        status=OnboardingStatus.PENDING.value,
        repo_local_path=body.repo_local_path,
        git_remote_url=body.git_remote_url,
        git_branch=body.git_branch,
        git_commit_sha=body.git_commit_sha,
        previous_onboarding_id=previous_id,
    )
    db.add(row)
    db.flush()

    AuditRepository(db).record(
        event_type=AuditEventType.ONBOARDING_STARTED,
        event_payload={
            "onboarding_id": str(row.id),
            "project_id": str(project_id),
            "git_commit_sha": body.git_commit_sha,
            "repo_local_path": body.repo_local_path,
        },
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
        project_id=project_id,
    )

    return _onboarding_begin_response(row)


# ── POST /scan ────────────────────────────────────────────────────────────────

@router.post("/scan", response_model=OnboardingScanResponse)
def run_scan(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    client_manifest: dict | None = None,
) -> OnboardingScanResponse:
    _require_member(db, user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    row = _get_active_onboarding_or_404(db, project_id)

    if row.status in _IMMUTABLE_STATUSES:
        raise HTTPException(status_code=409, detail="onboarding_already_approved")
    if row.status not in (
        OnboardingStatus.PENDING.value,
        OnboardingStatus.SCANNED.value,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"cannot_scan_from_status={row.status}",
        )

    row.status = OnboardingStatus.SCANNING.value
    db.flush()

    svc = OnboardingScanService(
        row.repo_local_path or "",
        client_manifest=client_manifest,
    )
    artifact = svc.run(git_commit_sha=row.git_commit_sha)

    row.scan_artifact_json = artifact
    row.status = OnboardingStatus.SCANNED.value

    primary_lang = (artifact.get("checks", {}).get("languages", {}).get("primary"))
    if primary_lang:
        row.language_primary = primary_lang
        langs = artifact.get("checks", {}).get("languages", {}).get("breakdown")
        if langs:
            row.languages_detected = langs
        frameworks = artifact.get("checks", {}).get("frameworks", {}).get("hints")
        if frameworks:
            row.framework_hints = frameworks

    db.flush()

    AuditRepository(db).record(
        event_type=AuditEventType.ONBOARDING_SCAN_COMPLETE,
        event_payload={
            "onboarding_id": str(row.id),
            "project_id": str(project_id),
            "git_commit_sha": row.git_commit_sha,
            "source": artifact.get("source", "unknown"),
            "gate_recommendation": artifact.get("gate_recommendation"),
            "secrets_findings_count": artifact.get("checks", {}).get("secrets_scan", {}).get("findings_count", -1),
        },
        actor_type=AuditActorType.USER,
        actor_id=str(user.id),
        project_id=project_id,
    )

    return OnboardingScanResponse(
        onboarding_id=row.id,
        project_id=row.project_id,
        status=row.status,
        scan_artifact_json=artifact,
    )


# ── GET /scan-result ──────────────────────────────────────────────────────────

@router.get("/scan-result", response_model=OnboardingScanResponse)
def get_scan_result(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OnboardingScanResponse:
    _require_member(db, user.id, project_id, ProjectMemberRole.VIEWER)
    row = _get_active_onboarding_or_404(db, project_id)
    return OnboardingScanResponse(
        onboarding_id=row.id,
        project_id=row.project_id,
        status=row.status,
        scan_artifact_json=row.scan_artifact_json,
    )


# ── GET /status ───────────────────────────────────────────────────────────────

@router.get("/status", response_model=OnboardingStatusResponse)
def get_onboarding_status(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OnboardingStatusResponse:
    _require_member(db, user.id, project_id, ProjectMemberRole.VIEWER)
    row = _get_active_onboarding_or_404(db, project_id)
    return _onboarding_status_response(row)
