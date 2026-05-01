"""100M — patch workflow API models."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class PatchProposeRequest(BaseModel):
    project_id: uuid.UUID
    directive_id: uuid.UUID
    agent_role: str = Field(..., min_length=1, max_length=32)
    user_id: uuid.UUID
    file_path: str = Field(..., min_length=1, max_length=4096)
    before_text: str = Field(..., max_length=2_000_000)
    after_text: str = Field(..., max_length=2_000_000)
    correlation_id: uuid.UUID | None = None


class PatchProposeResponse(BaseModel):
    unified_diff: str
    summary: str
    correlation_id: uuid.UUID
    result_text: str


class PatchRejectRequest(BaseModel):
    project_id: uuid.UUID
    directive_id: uuid.UUID
    agent_role: str = Field(..., min_length=1, max_length=32)
    user_id: uuid.UUID
    file_path: str = Field(..., min_length=1, max_length=4096)
    reason: str | None = Field(None, max_length=4096)
    correlation_id: uuid.UUID | None = None


class PatchRejectResponse(BaseModel):
    correlation_id: uuid.UUID


class PatchApplyCompleteRequest(BaseModel):
    project_id: uuid.UUID
    directive_id: uuid.UUID
    agent_role: str = Field(..., min_length=1, max_length=32)
    user_id: uuid.UUID
    file_path: str = Field(..., min_length=1, max_length=4096)
    unified_diff: str = Field(..., min_length=1, max_length=4_000_000)
    after_text: str = Field(..., max_length=2_000_000)
    correlation_id: uuid.UUID | None = None


class PatchApplyCompleteResponse(BaseModel):
    proof_object_id: uuid.UUID
    lock_id: uuid.UUID
    correlation_id: uuid.UUID
