from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEventRecord(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    workspace_id: uuid.UUID | None
    project_id: uuid.UUID | None
    directive_id: uuid.UUID | None
    event_type: str = Field(max_length=64)
    event_payload_json: dict[str, Any]
    actor_type: str = Field(max_length=32)
    actor_id: str | None
    created_at: datetime
