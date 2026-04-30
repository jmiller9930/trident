"""Request/response models for lock APIs (100E / 100P)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LockAcquireRequest(BaseModel):
    project_id: uuid.UUID
    directive_id: uuid.UUID
    agent_role: str = Field(..., min_length=1, max_length=32)
    user_id: uuid.UUID
    file_path: str = Field(..., min_length=1, max_length=4096)


class LockAcquireResponse(BaseModel):
    lock_id: uuid.UUID
    project_id: uuid.UUID
    directive_id: uuid.UUID
    file_path: str
    lock_status: str


class LockReleaseRequest(BaseModel):
    lock_id: uuid.UUID
    project_id: uuid.UUID
    directive_id: uuid.UUID
    agent_role: str = Field(..., min_length=1, max_length=32)
    user_id: uuid.UUID
    file_path: str = Field(..., min_length=1, max_length=4096)


class LockReleaseResponse(BaseModel):
    lock_id: uuid.UUID
    lock_status: str


class SimulatedMutationRequest(BaseModel):
    project_id: uuid.UUID
    directive_id: uuid.UUID
    agent_role: str = Field(..., min_length=1, max_length=32)
    user_id: uuid.UUID
    file_path: str = Field(..., min_length=1, max_length=4096)


class SimulatedMutationResponse(BaseModel):
    proof_object_id: uuid.UUID
    lock_id: uuid.UUID
    branch: str
    file_path: str


class LockActiveResponse(BaseModel):
    """Read-only active lock row (100P); excludes past expires_at."""

    lock_id: uuid.UUID
    project_id: uuid.UUID
    directive_id: uuid.UUID
    file_path: str
    locked_by_user_id: uuid.UUID
    locked_by_agent_role: str
    lock_status: str
    expires_at: datetime | None = None

