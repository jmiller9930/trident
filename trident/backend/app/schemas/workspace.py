from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceRecord(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str = Field(max_length=255)
    description: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
