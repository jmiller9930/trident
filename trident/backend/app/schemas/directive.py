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


class CreateDirectiveApiRequest(BaseModel):
    """Public API body; workspace and creator come from project + JWT."""

    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=4096)
    graph_id: str | None = Field(default=None, max_length=255)
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


class DirectiveIssueResponse(BaseModel):
    """Returned by POST /{id}/issue (GITHUB_004 — additive git fields, backward-compatible)."""
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
    # Git integration (additive; None when no repo linked or git disabled)
    git_branch_created: bool = False
    git_branch_name: str | None = None
    git_commit_sha: str | None = None
    git_warning: str | None = None


class DirectiveSignoffResponse(BaseModel):
    """Returned by POST /{id}/signoff (SIGNOFF_001)."""
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
    closed_at: datetime | None = None
    closed_by_user_id: uuid.UUID | None = None
    proof_object_id: uuid.UUID | None = None


class DirectiveDetailResponse(BaseModel):
    directive: DirectiveSummary
    task_ledger: TaskLedgerSummary


class DirectiveListResponse(BaseModel):
    items: list[DirectiveSummary]
