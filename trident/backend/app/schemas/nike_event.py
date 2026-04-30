from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator


class NikeEventIngestRequest(BaseModel):
    """Minimal Nike envelope (100O / 000P §6)."""

    event_id: uuid.UUID
    event_type: str = Field(..., min_length=1, max_length=128)
    source: str = Field(..., min_length=1, max_length=128)
    workspace_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    directive_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    correlation_id: uuid.UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def strip_event_type(cls, v: str) -> str:
        return v.strip()


class NikeEventIngestResponse(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    status: str
    idempotent_replay: bool = False


class NikeEventSnapshot(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_type: str
    source: str
    workspace_id: uuid.UUID | None
    project_id: uuid.UUID | None
    directive_id: uuid.UUID | None
    task_id: uuid.UUID | None
    correlation_id: uuid.UUID | None
    payload_json: dict[str, Any]
    status: str

    model_config = {"from_attributes": True}


class NikeEventListResponse(BaseModel):
    items: list[NikeEventSnapshot]
