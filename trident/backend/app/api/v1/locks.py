"""File lock + simulated mutation APIs (100E)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.locks.constants import LockStatus
from app.locks.exceptions import GitValidationError, LockConflictError, LockNotFoundError, LockOwnershipError
from app.locks.lock_service import LockService
from app.locks.simulated_mutation import SimulatedMutationPipeline
from app.schemas.locks import (
    LockAcquireRequest,
    LockAcquireResponse,
    LockReleaseRequest,
    LockReleaseResponse,
    SimulatedMutationRequest,
    SimulatedMutationResponse,
)

router = APIRouter()


@router.post("/acquire", response_model=LockAcquireResponse)
def acquire_lock(body: LockAcquireRequest, db: Session = Depends(get_db)) -> LockAcquireResponse:
    try:
        row = LockService(db).acquire(
            project_id=body.project_id,
            directive_id=body.directive_id,
            agent_role=body.agent_role,
            user_id=body.user_id,
            relative_file_path=body.file_path,
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
def release_lock(body: LockReleaseRequest, db: Session = Depends(get_db)) -> LockReleaseResponse:
    try:
        row = LockService(db).release(
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
