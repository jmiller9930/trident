from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectRecord(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str = Field(max_length=255)
    allowed_root_path: str
    git_remote_url: str | None
    created_at: datetime
    updated_at: datetime
