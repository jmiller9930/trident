from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OnboardingBeginRequest(BaseModel):
    repo_local_path: str = Field(min_length=1, max_length=4096)
    git_remote_url: str | None = Field(default=None, max_length=2048)
    git_branch: str | None = Field(default=None, max_length=255)
    git_commit_sha: str | None = Field(default=None, max_length=64)
    client_manifest: dict[str, Any] | None = Field(
        default=None,
        description="Pre-built scan manifest from VS Code extension when server cannot access path.",
    )


class OnboardingBeginResponse(BaseModel):
    onboarding_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    repo_local_path: str | None
    git_commit_sha: str | None
    created_at: datetime


class OnboardingScanResponse(BaseModel):
    onboarding_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    scan_artifact_json: dict[str, Any] | None


class OnboardingStatusResponse(BaseModel):
    onboarding_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    repo_local_path: str | None
    git_remote_url: str | None
    git_branch: str | None
    git_commit_sha: str | None
    language_primary: str | None
    index_job_id: str | None
    approved_by_user_id: uuid.UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    previous_onboarding_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
