from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GraphStateRecord(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    directive_id: uuid.UUID
    graph_id: str = Field(max_length=255)
    current_node: str | None = Field(default=None, max_length=255)
    state_payload_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
