"""IDE bootstrap API (100K / 100N / IDE_002) — chat, action, status, proof-summary."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ide.chat_service import process_ide_chat
from app.ide.ide_action_service import process_ide_action
from app.ide.ide_status_service import get_ide_proof_summary, get_ide_status
from app.schemas.ide_action import IdeActionRequest, IdeActionResponse
from app.schemas.ide_chat import IdeChatRequest, IdeChatResponse
from app.schemas.ide_status import IdeProofSummaryResponse, IdeStatusResponse

router = APIRouter()


@router.post("/action", response_model=IdeActionResponse)
def ide_action(body: IdeActionRequest, db: Session = Depends(get_db)) -> IdeActionResponse:
    """100N — governed orchestration; requires project_id + directive_id (no orphan IDE actions)."""
    try:
        return process_ide_action(db, body)
    except ValueError as e:
        code = str(e)
        if code == "directive_not_found":
            raise HTTPException(status_code=404, detail=code) from e
        if code == "directive_project_mismatch":
            raise HTTPException(status_code=400, detail=code) from e
        if code == "task_ledger_not_found":
            raise HTTPException(status_code=404, detail=code) from e
        if code == "workflow_already_complete":
            raise HTTPException(status_code=409, detail=code) from e
        if code == "invalid_agent_role":
            raise HTTPException(status_code=400, detail=code) from e
        if code in ("intent_required",):
            raise HTTPException(status_code=400, detail=code) from e
        if code == "unsupported_action":
            raise HTTPException(status_code=400, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e


@router.post("/chat", response_model=IdeChatResponse)
def ide_chat(body: IdeChatRequest, db: Session = Depends(get_db)) -> IdeChatResponse:
    try:
        reply, correlation_id, proof_object_id = process_ide_chat(
            db,
            directive_id=body.directive_id,
            prompt=body.prompt,
            actor_id=body.actor_id,
        )
    except ValueError as e:
        code = str(e)
        if code == "directive_not_found":
            raise HTTPException(status_code=404, detail=code) from e
        if code in ("prompt_empty", "prompt_too_long"):
            raise HTTPException(status_code=422, detail=code) from e
        raise HTTPException(status_code=400, detail=code) from e
    return IdeChatResponse(
        reply=reply,
        correlation_id=correlation_id,
        proof_object_id=proof_object_id,
    )


@router.get("/status/{directive_id}", response_model=IdeStatusResponse)
def ide_status(directive_id: uuid.UUID, db: Session = Depends(get_db)) -> IdeStatusResponse:
    """IDE_002 — lightweight polling endpoint: directive status + ledger + last routing decision."""
    try:
        return get_ide_status(db, directive_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/proof-summary/{directive_id}", response_model=IdeProofSummaryResponse)
def ide_proof_summary(directive_id: uuid.UUID, db: Session = Depends(get_db)) -> IdeProofSummaryResponse:
    """IDE_002 — audit + proof snapshot; returns only defined contract fields (no raw internal schema)."""
    try:
        return get_ide_proof_summary(db, directive_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
