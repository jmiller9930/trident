"""Decision engine API — TRIDENT_DECISION_ENGINE_001."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.db.session import get_db
from app.models.enums import ProjectMemberRole
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.services.decision_engine_service import DecisionEngineService, DecisionNotFoundError

router = APIRouter()


class EvidenceItemOut(BaseModel):
    source: str
    detail: str
    source_id: str | None = None


class DecisionResponse(BaseModel):
    recommendation: str
    confidence: float
    summary: str
    evidence: list[EvidenceItemOut]
    blocking_reasons: list[str]
    recommended_next_api_action: str | None = None
    computed_at: str


class DecisionRecordResponse(DecisionResponse):
    decision_record_id: uuid.UUID
    persisted: bool = True


def _require_role(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, minimum: ProjectMemberRole) -> None:
    try:
        MembershipRepository(db).require_role_at_least(user_id, project_id, minimum)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


def _output_to_response(output: Any) -> dict:
    return {
        "recommendation": output.recommendation,
        "confidence": output.confidence,
        "summary": output.summary,
        "evidence": [{"source": e.source, "detail": e.detail, "source_id": e.source_id} for e in output.evidence],
        "blocking_reasons": output.blocking_reasons,
        "recommended_next_api_action": output.recommended_next_api_action,
        "computed_at": output.computed_at.isoformat(),
    }


@router.get("/decision", response_model=DecisionResponse)
def get_decision(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    patch_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DecisionResponse:
    """Compute live decision without persistence. VIEWER+."""
    _require_role(db, user.id, project_id, ProjectMemberRole.VIEWER)
    try:
        output = DecisionEngineService(db).compute(project_id, directive_id, patch_id)
    except DecisionNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return DecisionResponse(**_output_to_response(output))


@router.post("/decision/record", response_model=DecisionRecordResponse, status_code=201)
def record_decision(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    patch_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DecisionRecordResponse:
    """Compute and persist decision record. CONTRIBUTOR+."""
    _require_role(db, user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    try:
        output, row = DecisionEngineService(db).record(project_id, directive_id, user.id, patch_id)
    except DecisionNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    return DecisionRecordResponse(
        **_output_to_response(output),
        decision_record_id=row.id,
        persisted=True,
    )
