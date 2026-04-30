from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HandoffRecord(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    directive_id: uuid.UUID
    from_agent_role: str = Field(max_length=32)
    to_agent_role: str = Field(max_length=32)
    handoff_payload_json: dict[str, Any]
    requires_ack: bool
    acknowledged_at: datetime | None
    created_at: datetime
