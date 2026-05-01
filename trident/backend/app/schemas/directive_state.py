"""DirectiveStateResponse — single-source-of-truth UI state aggregate (STATUS_001).

Consumed by the VS Code workbench so no client-side guessing is needed.
All fields are computed server-side; clients render what they receive.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


# ── Sub-sections ──────────────────────────────────────────────────────────────

class DirectiveCoreSummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    workspace_id: uuid.UUID
    project_id: uuid.UUID
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    closed_by_user_id: uuid.UUID | None = None


class GitState(BaseModel):
    repo_linked: bool
    clone_url: str | None = None
    default_branch: str | None = None
    active_branch: str | None = None
    commit_sha: str | None = None
    branch_created_for_directive: bool = False
    directive_branch_name: str | None = None


class PatchStateSummary(BaseModel):
    total: int = 0
    proposed: int = 0
    accepted: int = 0
    rejected: int = 0
    executed: int = 0
    latest_patch_id: uuid.UUID | None = None
    latest_patch_status: str | None = None
    latest_patch_title: str | None = None
    latest_execution_commit_sha: str | None = None
    latest_execution_branch_name: str | None = None


class ValidationStateSummary(BaseModel):
    total: int = 0
    pending: int = 0
    running: int = 0
    passed: int = 0
    failed: int = 0
    waived: int = 0
    latest_run_id: uuid.UUID | None = None
    latest_run_status: str | None = None
    latest_run_type: str | None = None


class SignoffState(BaseModel):
    eligible: bool = False
    blocking_reasons: list[str] = []


class AllowedAction(BaseModel):
    action: str
    label: str
    enabled: bool
    disabled_reason: str | None = None


# ── Lifecycle phase ───────────────────────────────────────────────────────────

_PHASE_MAP: dict[str, str] = {
    "DRAFT": "authoring",
    "ISSUED": "active",
    "ACTIVE": "active",
    "IN_PROGRESS": "active",
    "BUILDING": "active",
    "REVIEW": "review",
    "PROOF_RETURNED": "review",
    "PROOF_ACCEPTED": "review",
    "BUG_CHECKING": "review",
    "SIGNED_OFF": "completing",
    "COMPLETE": "done",
    "CLOSED": "done",
    "REJECTED": "done",
    "CANCELLED": "done",
    "BLOCKED": "blocked",
}


def lifecycle_phase(status: str) -> str:
    return _PHASE_MAP.get(status, "unknown")


# ── Top-level response ────────────────────────────────────────────────────────

class DirectiveStateResponse(BaseModel):
    """Full state aggregate for a directive — consumed by VS Code workbench."""

    directive: DirectiveCoreSummary
    lifecycle_phase: str
    git: GitState
    patches: PatchStateSummary
    validations: ValidationStateSummary
    signoff: SignoffState
    allowed_actions: list[AllowedAction]
    as_of: datetime
