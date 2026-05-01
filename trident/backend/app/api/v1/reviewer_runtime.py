"""Reviewer agent runtime API — TRIDENT_AGENT_REVIEWER_001."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.config.settings import Settings
from app.db.session import get_db, get_settings_dep
from app.models.enums import ProjectMemberRole
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.services.reviewer_runtime_service import (
    ReviewerOutputParseError,
    ReviewerRuntimeBlockedError,
    ReviewerRuntimeService,
)

router = APIRouter()


class ReviewerRunRequest(BaseModel):
    instruction: str | None = Field(default=None, max_length=4096)


class ReviewFindingOut(BaseModel):
    severity: str
    message: str
    path: str | None = None
    suggested_action: str | None = None


class ReviewerRunResponse(BaseModel):
    review_id: uuid.UUID
    recommendation: str
    confidence: float
    summary: str
    findings: list[ReviewFindingOut]
    model_routing_trace: dict[str, Any] | None = None


@router.post("/agents/reviewer/run", response_model=ReviewerRunResponse, status_code=201)
def run_reviewer_agent(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    patch_id: uuid.UUID,
    body: ReviewerRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    cfg: Settings = Depends(get_settings_dep),
) -> ReviewerRunResponse:
    """Run the Reviewer agent once for this patch proposal. CONTRIBUTOR+."""
    try:
        MembershipRepository(db).require_role_at_least(user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    svc = ReviewerRuntimeService(db, cfg)
    try:
        result = svc.run_reviewer(
            project_id=project_id,
            directive_id=directive_id,
            patch_id=patch_id,
            user_id=user.id,
            instruction=body.instruction,
        )
    except ReviewerRuntimeBlockedError as e:
        code = str(e)
        status = 409 if "closed" in code or "not_proposed" in code else 422
        raise HTTPException(status_code=status, detail=code) from None
    except ReviewerOutputParseError as e:
        raise HTTPException(status_code=422, detail=f"reviewer_output_invalid:{e}") from None

    return ReviewerRunResponse(
        review_id=result.review_id,
        recommendation=result.recommendation,
        confidence=result.confidence,
        summary=result.summary,
        findings=[ReviewFindingOut(**f) for f in result.findings],
        model_routing_trace=result.model_routing_trace,
    )
