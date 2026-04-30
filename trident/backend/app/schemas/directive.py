from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import DirectiveStatus


class CreateDirectiveRequest(BaseModel):
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=4096)
    graph_id: str | None = Field(default=None, max_length=255)
    created_by_user_id: uuid.UUID
    status: DirectiveStatus = DirectiveStatus.DRAFT


class TaskLedgerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    directive_id: uuid.UUID
    current_state: str
    current_agent_role: str
    current_owner_user_id: uuid.UUID | None
    last_transition_at: datetime
    created_at: datetime
    updated_at: datetime


class DirectiveSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    title: str
    status: str
    graph_id: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DirectiveDetailResponse(BaseModel):
    directive: DirectiveSummary
    task_ledger: TaskLedgerSummary


class DirectiveListResponse(BaseModel):
    items: list[DirectiveSummary]
