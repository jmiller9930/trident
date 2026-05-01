"""File lock + simulated mutation APIs (100E / FIX 003)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.session import get_db, get_settings_dep
from app.locks.constants import LockStatus
from app.locks.exceptions import GitValidationError, LockConflictError, LockNotFoundError, LockOwnershipError
from app.locks.lock_liveness import apply_stale_transition_if_missed
from app.locks.lock_service import LockService, normalize_relative_file_path
from app.locks.lock_validator import find_active_lock
from app.locks.simulated_mutation import SimulatedMutationPipeline
from app.models.file_lock import FileLock
from app.schemas.locks import (
    LockAcquireRequest,
    LockAcquireResponse,
    LockActiveResponse,
    LockForceReleaseRequest,
    LockForceReleaseResponse,
    LockHeartbeatResponse,
    LockPathStatusResponse,
    LockReleaseRequest,
    LockReleaseResponse,
    SimulatedMutationRequest,
    SimulatedMutationResponse,
)

router = APIRouter()


def _lock_path_status_rows(db: Session, project_id: uuid.UUID, fp: str, cfg: Settings) -> LockPathStatusResponse:
    rows = list(
        db.scalars(
            select(FileLock)
            .where(FileLock.project_id == project_id, FileLock.file_path == fp)
            .order_by(desc(FileLock.created_at))
            .limit(32)
        ).all()
    )
    active = next((r for r in rows if r.lock_status == LockStatus.ACTIVE.value and r.released_at is None), None)
    if active is not None:
        apply_stale_transition_if_missed(db, active, cfg)
        db.refresh(active)
        if active.lock_status == LockStatus.ACTIVE.value:
            return LockPathStatusResponse(
                present=True,
                lock_id=active.id,
                lock_status=active.lock_status,
                directive_id=active.directive_id,
                locked_by_user_id=active.locked_by_user_id,
                last_heartbeat_at=active.last_heartbeat_at,
            )
    stale = next((r for r in rows if r.lock_status == LockStatus.STALE_PENDING_RECOVERY.value and r.released_at is None), None)
    if stale is not None:
        return LockPathStatusResponse(
            present=True,
            lock_id=stale.id,
            lock_status=stale.lock_status,
            directive_id=stale.directive_id,
            locked_by_user_id=stale.locked_by_user_id,
            last_heartbeat_at=stale.last_heartbeat_at,
        )
    if rows:
        head = rows[0]
        return LockPathStatusResponse(
            present=True,
            lock_id=head.id,
            lock_status=head.lock_status,
            directive_id=head.directive_id,
            locked_by_user_id=head.locked_by_user_id,
            last_heartbeat_at=head.last_heartbeat_at,
        )
    return LockPathStatusResponse(present=False)


@router.get("/status", response_model=LockPathStatusResponse)
def lock_path_status(
    project_id: uuid.UUID = Query(...),
    file_path: str = Query(..., min_length=1, max_length=4096),
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> LockPathStatusResponse:
    try:
        fp = normalize_relative_file_path(file_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _lock_path_status_rows(db, project_id, fp, cfg)


@router.get("/active", response_model=LockActiveResponse)
def get_active_lock(
    project_id: uuid.UUID = Query(...),
    file_path: str = Query(..., min_length=1, max_length=4096),
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> LockActiveResponse:
    """Read-only: editable ACTIVE lock for project + relative path."""
    try:
        fp = normalize_relative_file_path(file_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    row = find_active_lock(db, project_id=project_id, file_path_normalized=fp, settings=cfg)
    if row is None:
        raise HTTPException(status_code=404, detail="no_active_lock")
    return LockActiveResponse(
        lock_id=row.id,
        project_id=row.project_id,
        directive_id=row.directive_id,
        file_path=row.file_path,
        locked_by_user_id=row.locked_by_user_id,
        locked_by_agent_role=row.locked_by_agent_role,
        lock_status=row.lock_status,
        expires_at=row.expires_at,
        last_heartbeat_at=row.last_heartbeat_at,
    )


@router.post("/heartbeat", response_model=LockHeartbeatResponse)
def lock_heartbeat(
    body: LockReleaseRequest,
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> LockHeartbeatResponse:
    """FIX 003 — same identity envelope as release; refreshes last_heartbeat_at."""
    _ = cfg  # settings hook for future policy
    try:
        row = LockService(db, cfg).heartbeat(
            lock_id=body.lock_id,
            project_id=body.project_id,
            directive_id=body.directive_id,
            agent_role=body.agent_role,
            user_id=body.user_id,
            relative_file_path=body.file_path,
        )
    except LockNotFoundError:
        raise HTTPException(status_code=404, detail="lock_not_found") from None
    except LockOwnershipError:
        raise HTTPException(status_code=403, detail="lock_ownership_mismatch") from None
    return LockHeartbeatResponse(lock_id=row.id, lock_status=row.lock_status)


@router.post("/force-release", response_model=LockForceReleaseResponse)
def lock_force_release(
    body: LockForceReleaseRequest,
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> LockForceReleaseResponse:
    """FIX 003 — admin allowlist in TRIDENT_LOCK_FORCE_RELEASE_ADMIN_USER_IDS."""
    try:
        row = LockService(db, cfg).force_release(
            lock_id=body.lock_id,
            project_id=body.project_id,
            admin_user_id=body.admin_user_id,
        )
    except LockNotFoundError:
        raise HTTPException(status_code=404, detail="lock_not_found") from None
    except LockOwnershipError:
        raise HTTPException(status_code=400, detail="project_mismatch") from None
    except PermissionError:
        raise HTTPException(status_code=403, detail="force_release_forbidden") from None
    return LockForceReleaseResponse(lock_id=row.id, lock_status=row.lock_status)


@router.post("/acquire", response_model=LockAcquireResponse)
def acquire_lock(
    body: LockAcquireRequest,
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> LockAcquireResponse:
    ttl = cfg.lock_ttl_sec if cfg.lock_ttl_sec > 0 else None
    try:
        row = LockService(db, cfg).acquire(
            project_id=body.project_id,
            directive_id=body.directive_id,
            agent_role=body.agent_role,
            user_id=body.user_id,
            relative_file_path=body.file_path,
            ttl_seconds=ttl,
        )
    except LockConflictError:
        raise HTTPException(status_code=409, detail="lock_conflict") from None
    except ValueError as e:
        code = str(e)
        if code == "directive_not_found":
            raise HTTPException(status_code=404, detail=code) from e
        if code == "directive_project_mismatch":
            raise HTTPException(status_code=400, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e
    return LockAcquireResponse(
        lock_id=row.id,
        project_id=row.project_id,
        directive_id=row.directive_id,
        file_path=row.file_path,
        lock_status=row.lock_status,
    )


@router.post("/release", response_model=LockReleaseResponse)
def release_lock(
    body: LockReleaseRequest,
    db: Session = Depends(get_db),
    cfg: Settings = Depends(get_settings_dep),
) -> LockReleaseResponse:
    try:
        row = LockService(db, cfg).release(
            lock_id=body.lock_id,
            project_id=body.project_id,
            directive_id=body.directive_id,
            agent_role=body.agent_role,
            user_id=body.user_id,
            relative_file_path=body.file_path,
        )
    except LockNotFoundError:
        raise HTTPException(status_code=404, detail="lock_not_found") from None
    except LockOwnershipError:
        raise HTTPException(status_code=403, detail="lock_ownership_mismatch") from None
    return LockReleaseResponse(lock_id=row.id, lock_status=LockStatus.RELEASED.value)


@router.post("/simulated-mutation", response_model=SimulatedMutationResponse)
def simulated_mutation(body: SimulatedMutationRequest, db: Session = Depends(get_db)) -> SimulatedMutationResponse:
    try:
        out = SimulatedMutationPipeline(db).run(
            project_id=body.project_id,
            directive_id=body.directive_id,
            agent_role=body.agent_role,
            user_id=body.user_id,
            relative_file_path=body.file_path,
        )
    except GitValidationError as e:
        detail = str(e.args[0]) if e.args else "git_validation_failed"
        raise HTTPException(status_code=400, detail=detail) from e
    except LockNotFoundError:
        raise HTTPException(status_code=404, detail="no_active_lock") from None
    except LockOwnershipError:
        raise HTTPException(status_code=403, detail="lock_ownership_mismatch") from None
    except ValueError as e:
        code = str(e)
        if code in ("directive_not_found", "project_not_found"):
            raise HTTPException(status_code=404, detail=code) from e
        if code == "directive_project_mismatch":
            raise HTTPException(status_code=400, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e

    pid = out["proof_object_id"]
    lid = out["lock_id"]
    if not isinstance(pid, uuid.UUID):
        pid = uuid.UUID(str(pid))
    if not isinstance(lid, uuid.UUID):
        lid = uuid.UUID(str(lid))
    return SimulatedMutationResponse(
        proof_object_id=pid,
        lock_id=lid,
        branch=str(out["branch"]),
        file_path=str(out["file_path"]),
    )
