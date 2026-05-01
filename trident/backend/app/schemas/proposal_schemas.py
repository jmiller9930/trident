"""Pydantic schemas for governed patch proposal endpoints (PATCH_001)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PatchProposalCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    summary: str | None = Field(default=None, max_length=8192)
    files_changed: dict[str, Any] | None = None
    unified_diff: str | None = Field(default=None, max_length=10_000_000)
    proposed_by_agent_role: str | None = Field(default=None, max_length=32)


class PatchProposalRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4096)


class PatchProposalSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    project_id: uuid.UUID
    directive_id: uuid.UUID
    status: str
    title: str
    summary: str | None
    proposed_by_user_id: uuid.UUID | None
    proposed_by_agent_role: str | None
    accepted_by_user_id: uuid.UUID | None
    accepted_at: datetime | None
    rejected_by_user_id: uuid.UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class PatchProposalDetail(PatchProposalSummary):
    files_changed: dict[str, Any] | None = None
    unified_diff: str | None = None


class PatchProposalListResponse(BaseModel):
    items: list[PatchProposalSummary]


class PatchProposalAcceptResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    status: str
    accepted_by_user_id: uuid.UUID | None
    accepted_at: datetime | None
    proof_object_id: uuid.UUID | None = None


class PatchProposalRejectResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    status: str
    rejected_by_user_id: uuid.UUID | None
    rejected_at: datetime | None
    rejection_reason: str | None


class PatchExecuteResponse(BaseModel):
    patch_id: uuid.UUID
    execution_status: str
    commit_sha: str
    branch_name: str
    proof_object_id: uuid.UUID | None = None
    executed_at: datetime | None = None
    executed_by_user_id: uuid.UUID | None = None
