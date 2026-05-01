"""100M — patch propose / reject / apply-complete."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.session import get_db, get_settings_dep
from app.locks.exceptions import GitValidationError, LockNotFoundError, LockOwnershipError
from app.patches.patch_pipeline import PatchWorkflowService
from app.schemas.patches import (
    PatchApplyCompleteRequest,
    PatchApplyCompleteResponse,
    PatchProposeRequest,
    PatchProposeResponse,
    PatchRejectRequest,
    PatchRejectResponse,
)

router = APIRouter()


@router.post("/propose", response_model=PatchProposeResponse)
def patch_propose(body: PatchProposeRequest, db: Session = Depends(get_db), cfg: Settings = Depends(get_settings_dep)) -> PatchProposeResponse:
    svc = PatchWorkflowService(db, cfg)
    try:
        diff_text, summary, cid = svc.propose(
            project_id=body.project_id,
            directive_id=body.directive_id,
            agent_role=body.agent_role,
            user_id=body.user_id,
            relative_file_path=body.file_path,
            before_text=body.before_text,
            after_text=body.after_text,
            correlation_id=body.correlation_id,
        )
    except GitValidationError as e:
        detail = str(e.args[0]) if e.args else "git_validation_failed"
        raise HTTPException(status_code=400, detail=detail) from e
    except ValueError as e:
        code = str(e)
        if code in ("directive_not_found", "project_not_found"):
            raise HTTPException(status_code=404, detail=code) from e
        if code in (
            "directive_project_mismatch",
            "hidden_path_segment_forbidden",
        ):
            raise HTTPException(status_code=400, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e

    return PatchProposeResponse(
        unified_diff=diff_text,
        summary=summary,
        correlation_id=cid,
        result_text=body.after_text,
    )


@router.post("/reject", response_model=PatchRejectResponse)
def patch_reject(body: PatchRejectRequest, db: Session = Depends(get_db), cfg: Settings = Depends(get_settings_dep)) -> PatchRejectResponse:
    _ = cfg
    svc = PatchWorkflowService(db, cfg)
    try:
        cid = svc.reject(
            project_id=body.project_id,
            directive_id=body.directive_id,
            agent_role=body.agent_role,
            user_id=body.user_id,
            relative_file_path=body.file_path,
            reason=body.reason,
            correlation_id=body.correlation_id,
        )
    except ValueError as e:
        code = str(e)
        if code == "directive_not_found":
            raise HTTPException(status_code=404, detail=code) from e
        if code in ("directive_project_mismatch", "hidden_path_segment_forbidden"):
            raise HTTPException(status_code=400, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e

    return PatchRejectResponse(correlation_id=cid)


@router.post("/apply-complete", response_model=PatchApplyCompleteResponse)
def patch_apply_complete(
    body: PatchApplyCompleteRequest, db: Session = Depends(get_db), cfg: Settings = Depends(get_settings_dep)
) -> PatchApplyCompleteResponse:
    svc = PatchWorkflowService(db, cfg)
    try:
        out = svc.apply_complete(
            project_id=body.project_id,
            directive_id=body.directive_id,
            agent_role=body.agent_role,
            user_id=body.user_id,
            relative_file_path=body.file_path,
            unified_diff=body.unified_diff,
            after_text=body.after_text,
            correlation_id=body.correlation_id,
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
        if code == "hidden_path_segment_forbidden":
            raise HTTPException(status_code=400, detail=code) from e
        if code == "patch_disk_verification_failed":
            raise HTTPException(status_code=400, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e

    pid = out["proof_object_id"]
    lid = out["lock_id"]
    cid = out["correlation_id"]
    if not isinstance(pid, uuid.UUID):
        pid = uuid.UUID(str(pid))
    if not isinstance(lid, uuid.UUID):
        lid = uuid.UUID(str(lid))
    if not isinstance(cid, uuid.UUID):
        cid = uuid.UUID(str(cid))

    return PatchApplyCompleteResponse(proof_object_id=pid, lock_id=lid, correlation_id=cid)
