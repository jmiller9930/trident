from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class MemoryWriteRequest(BaseModel):
    directive_id: uuid.UUID
    task_id: uuid.UUID
    agent_role: str = Field(..., min_length=1, max_length=32)
    workflow_context_marker: str = Field(..., min_length=8, max_length=512)
    memory_kind: str = Field(..., min_length=1, max_length=32)
    title: str | None = Field(default=None, max_length=512)
    body: str = Field(..., min_length=1, max_length=65536)
    payload: dict[str, Any] = Field(default_factory=dict)


class MemoryWriteResponse(BaseModel):
    memory_entry_id: uuid.UUID
    chroma_document_id: str | None
    memory_sequence: int
    vector_state: str


class MemoryRetryVectorRequest(BaseModel):
    directive_id: uuid.UUID
    task_id: uuid.UUID
    agent_role: str = Field(..., min_length=1, max_length=32)
    workflow_context_marker: str = Field(..., min_length=8, max_length=512)
    memory_entry_id: uuid.UUID


class MemoryRetryVectorResponse(BaseModel):
    memory_entry_id: uuid.UUID
    chroma_document_id: str | None
    vector_state: str
