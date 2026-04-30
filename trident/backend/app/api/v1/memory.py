"""Memory read/write API (100D). Writes require active workflow nonce."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.memory.exceptions import MemoryWriteForbidden
from app.memory.memory_reader import MemoryReader
from app.memory.memory_writer import MemoryWriter
from app.schemas.memory import MemoryWriteRequest, MemoryWriteResponse

router = APIRouter()


@router.get("/project/{project_id}")
def memory_for_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
) -> dict:
    return MemoryReader(db).read_project(project_id, limit=limit)


@router.get("/directive/{directive_id}")
def memory_for_directive(
    directive_id: uuid.UUID,
    db: Session = Depends(get_db),
    q: str | None = Query(None, description="Optional semantic query (Chroma)."),
    top_k: int = Query(8, ge=1, le=32),
) -> dict:
    data = MemoryReader(db).read_directive(directive_id, vector_query=q, vector_top_k=top_k)
    if data.get("error") == "directive_not_found":
        raise HTTPException(status_code=404, detail="directive_not_found")
    if data.get("error") == "task_ledger_not_found":
        raise HTTPException(status_code=404, detail="task_ledger_not_found")
    return data


@router.post("/write", response_model=MemoryWriteResponse)
def memory_write_guarded(body: MemoryWriteRequest, db: Session = Depends(get_db)) -> MemoryWriteResponse:
    """Guarded write: requires task_id = task_ledger.id, matching agent_role, valid workflow nonce."""
    try:
        row = MemoryWriter(db).write_via_guarded_api(
            directive_id=body.directive_id,
            task_ledger_id=body.task_id,
            agent_role=body.agent_role.strip(),
            workflow_run_nonce=body.workflow_context_marker.strip(),
            title=body.title,
            body=body.body,
            memory_kind=body.memory_kind.strip(),
            payload=body.payload,
        )
    except MemoryWriteForbidden as e:
        raise HTTPException(status_code=403, detail=e.code) from e
    return MemoryWriteResponse(memory_entry_id=row.id, chroma_document_id=row.chroma_document_id)
