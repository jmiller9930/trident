"""100N — governed IDE orchestration (single backend entrypoint)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


IdeActionKind = Literal["ASK", "RUN_WORKFLOW", "PROPOSE_PATCH"]


class IdeActionRequest(BaseModel):
    """project_id + directive_id required — orphan IDE actions are rejected (100N)."""

    project_id: uuid.UUID
    directive_id: uuid.UUID
    agent_role: str = Field(..., min_length=1, max_length=32)
    action: IdeActionKind
    prompt: str | None = Field(None, max_length=16_384)
    intent_for_router: str | None = Field(None, max_length=8192)
    reviewer_rejections_remaining: int = Field(0, ge=0, le=32)
    actor_id: str | None = Field(None, max_length=512)

    @model_validator(mode="after")
    def _prompt_for_ask(self) -> IdeActionRequest:
        if self.action == "ASK":
            if not (self.prompt or "").strip():
                raise ValueError("prompt_required_for_ask")
        return self


class IdeRouterSnapshot(BaseModel):
    route: str | None = None
    reason: str = ""
    next_action: str = ""
    validated: bool = False


class IdeMcpAuditSnippet(BaseModel):
    event_type: str
    created_at: str | None = None
    payload_preview: str = ""


class IdeActionResponse(BaseModel):
    correlation_id: uuid.UUID
    action: str
    project_id: uuid.UUID
    directive_id: uuid.UUID
    directive_status: str
    task_ledger_state: str
    current_agent_role: str
    reply: str | None = None
    nodes_executed: list[str] | None = None
    proof_object_id: uuid.UUID | None = None
    router: IdeRouterSnapshot | None = None
    memory_preview: dict[str, Any] | None = None
    mcp_recent: list[IdeMcpAuditSnippet] | None = None
    patch_guidance: str | None = None
