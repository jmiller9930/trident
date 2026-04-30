from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserRecord(BaseModel):
    """API-facing user summary (100B baseline)."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    display_name: str = Field(max_length=255)
    email: str = Field(max_length=512)
    role: str = Field(max_length=64)
    created_at: datetime
    updated_at: datetime
