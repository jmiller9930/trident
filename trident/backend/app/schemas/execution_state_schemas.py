"""Execution state aggregate schemas (STATUS_001 — execution-state endpoint).

Response is the VS Code workbench source of truth for directive state.
Every field is DB-derived. No client inference.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DirectiveStateSummary(BaseModel):
    directive_id: uuid.UUID
    project_id: uuid.UUID
    title: str
    status: str
    created_by_user_id: uuid.UUID
    created_at: datetime
    closed_at: datetime | None = None
    closed_by_user_id: uuid.UUID | None = None


class GitStateSummary(BaseModel):
    repo_linked: bool
    provider: str | None = None
    owner: str | None = None
    repo_name: str | None = None
    branch_name: str | None = None
    latest_commit_sha: str | None = None
    branch_created: bool = False
    commit_pushed: bool = False


class PatchStateSummary(BaseModel):
    patch_count: int = 0
    latest_patch_id: uuid.UUID | None = None
    latest_patch_status: str | None = None
    accepted_patch_id: uuid.UUID | None = None
    accepted_patch_executed: bool = False
    execution_commit_sha: str | None = None


class ValidationStateSummary(BaseModel):
    validation_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    waived_count: int = 0
    latest_validation_status: str | None = None
    signoff_eligible: bool = False


class SignoffStateSummary(BaseModel):
    closed: bool = False
    proof_object_id: uuid.UUID | None = None


class ActionAllowed(BaseModel):
    allowed: bool
    reason_code: str | None = None
    reason_text: str | None = None


class ActionsAllowed(BaseModel):
    create_patch: ActionAllowed
    accept_patch: ActionAllowed
    reject_patch: ActionAllowed
    execute_patch: ActionAllowed
    create_validation: ActionAllowed
    start_validation: ActionAllowed
    complete_validation: ActionAllowed
    waive_validation: ActionAllowed
    signoff: ActionAllowed


class BlockingReason(BaseModel):
    code: str
    message: str
    required_next_action: str | None = None


class ExecutionStateResponse(BaseModel):
    """Workbench source of truth. DB-derived, read-only, no provider calls."""
    directive: DirectiveStateSummary
    git: GitStateSummary
    patch: PatchStateSummary
    validation: ValidationStateSummary
    signoff: SignoffStateSummary
    actions_allowed: ActionsAllowed
    blocking_reasons: list[BlockingReason]
    computed_at: datetime
