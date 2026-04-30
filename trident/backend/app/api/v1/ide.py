"""IDE bootstrap API (100K) — deterministic chat stub."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ide.chat_service import process_ide_chat
from app.schemas.ide_chat import IdeChatRequest, IdeChatResponse

router = APIRouter()


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
