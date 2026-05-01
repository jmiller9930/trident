from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    allowed_root_path: str = Field(default="/", min_length=1, max_length=4096)
    git_remote_url: str | None = Field(default=None, max_length=2048)


class ProjectSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    allowed_root_path: str
    git_remote_url: str | None
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    items: list[ProjectSummary]
