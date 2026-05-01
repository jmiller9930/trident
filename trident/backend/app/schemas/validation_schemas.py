"""Pydantic schemas for validation run endpoints (VALIDATION_001)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.validation_run import ValidationRunType


class ValidationRunCreateRequest(BaseModel):
    validation_type: ValidationRunType = ValidationRunType.MANUAL
    patch_id: uuid.UUID | None = None
    commit_sha: str | None = Field(default=None, max_length=64)
    result_summary: str | None = Field(default=None, max_length=8192)
    result_payload_json: dict[str, Any] | None = None


class ValidationRunCompleteRequest(BaseModel):
    passed: bool
    result_summary: str = Field(min_length=1, max_length=8192)
    result_payload_json: dict[str, Any] | None = None


class ValidationRunWaiveRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4096)


class ValidationRunSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    project_id: uuid.UUID
    directive_id: uuid.UUID
    patch_id: uuid.UUID | None
    commit_sha: str | None
    status: str
    validation_type: str
    result_summary: str | None
    started_by_user_id: uuid.UUID
    completed_by_user_id: uuid.UUID | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ValidationRunDetail(ValidationRunSummary):
    result_payload_json: dict[str, Any] | None = None
    proof_object_id: uuid.UUID | None = None


class ValidationRunListResponse(BaseModel):
    items: list[ValidationRunSummary]
