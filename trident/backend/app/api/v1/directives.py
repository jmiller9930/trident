from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.directive_repository import DirectiveRepository
from app.repositories.task_ledger_repository import TaskLedgerRepository
from app.schemas.directive import (
    CreateDirectiveRequest,
    DirectiveDetailResponse,
    DirectiveListResponse,
    DirectiveSummary,
    TaskLedgerSummary,
)

router = APIRouter()


@router.post("/", response_model=DirectiveDetailResponse)
def create_directive(body: CreateDirectiveRequest, db: Session = Depends(get_db)) -> DirectiveDetailResponse:
    repo = DirectiveRepository(db)
    try:
        directive, ledger, _gs = repo.create_directive_and_initialize(body)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return DirectiveDetailResponse(
        directive=DirectiveSummary.model_validate(directive),
        task_ledger=TaskLedgerSummary.model_validate(ledger),
    )


@router.get("/", response_model=DirectiveListResponse)
def list_directives(db: Session = Depends(get_db), limit: int = 100) -> DirectiveListResponse:
    repo = DirectiveRepository(db)
    rows = repo.list_summaries(limit=limit)
    return DirectiveListResponse(items=[DirectiveSummary.model_validate(r) for r in rows])


@router.get("/{directive_id}", response_model=DirectiveDetailResponse)
def get_directive(directive_id: uuid.UUID, db: Session = Depends(get_db)) -> DirectiveDetailResponse:
    drepo = DirectiveRepository(db)
    trepo = TaskLedgerRepository(db)
    d = drepo.get_by_id(directive_id)
    if d is None:
        raise HTTPException(status_code=404, detail="directive_not_found")
    ledger = trepo.get_by_directive_id(directive_id)
    if ledger is None:
        raise HTTPException(status_code=404, detail="task_ledger_not_found")
    return DirectiveDetailResponse(
        directive=DirectiveSummary.model_validate(d),
        task_ledger=TaskLedgerSummary.model_validate(ledger),
    )
