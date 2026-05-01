"""Agent runtime API — governed Engineer agent run (TRIDENT_AGENT_RUNTIME_001)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps.auth_deps import get_current_user
from app.db.session import get_db, get_settings_dep
from app.config.settings import Settings
from app.models.enums import ProjectMemberRole
from app.models.user import User
from app.repositories.membership_repository import MembershipRepository
from app.services.agent_runtime_service import (
    AgentOutputParseError,
    AgentRuntimeBlockedError,
    AgentRuntimeService,
)
from app.services.execution_state_service import (
    ExecutionStateNotFoundError,
    ExecutionStateMismatchError,
    ExecutionStateService,
)

router = APIRouter()


# ── Request / response ────────────────────────────────────────────────────────

class EngineerRunRequest(BaseModel):
    instruction: str | None = None


class EngineerRunResponse(BaseModel):
    patch_id: uuid.UUID
    title: str
    summary: str
    model_routing_trace: dict | None = None
    status: str = "PROPOSED"


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/engineer/run", response_model=EngineerRunResponse, status_code=201)
def run_engineer_agent(
    project_id: uuid.UUID,
    directive_id: uuid.UUID,
    body: EngineerRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    cfg: Settings = Depends(get_settings_dep),
) -> EngineerRunResponse:
    """Run the Engineer agent once for this directive.

    Preconditions (checked here and in service):
    - Caller is CONTRIBUTOR+ on the project.
    - Directive is ISSUED and not CLOSED.
    - create_patch action is allowed per execution-state.
    """
    # RBAC
    try:
        MembershipRepository(db).require_role_at_least(user.id, project_id, ProjectMemberRole.CONTRIBUTOR)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    # Fetch execution-state to pass allowed_actions downstream (no duplicate DB queries)
    try:
        es = ExecutionStateService(db).get_execution_state(directive_id, project_id, user.id)
        allowed_actions = {
            k: {"allowed": getattr(v, "allowed", False), "reason_code": getattr(v, "reason_code", None)}
            for k, v in es.actions_allowed.__dict__.items()
        }
    except (ExecutionStateNotFoundError, ExecutionStateMismatchError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    svc = AgentRuntimeService(db, cfg)
    try:
        result = svc.run_engineer(
            project_id=project_id,
            directive_id=directive_id,
            user_id=user.id,
            instruction=body.instruction,
            allowed_actions_from_state=allowed_actions,
        )
    except AgentRuntimeBlockedError as e:
        code = str(e)
        status = 409 if code in ("directive_closed", "directive_already_closed") else 422
        raise HTTPException(status_code=status, detail=code) from None
    except AgentOutputParseError as e:
        raise HTTPException(status_code=422, detail=f"agent_output_invalid:{e}") from None

    safe_trace = {
        k: v
        for k, v in result.model_routing_trace.items()
        if k not in ("signal_breakdown",)  # exclude verbose internals
    }

    return EngineerRunResponse(
        patch_id=result.patch_id,
        title=result.title,
        summary=result.summary,
        model_routing_trace=safe_trace,
        status="PROPOSED",
    )
