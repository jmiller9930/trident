"""IDE chat stub request/response (100K — deterministic, audited)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class IdeChatRequest(BaseModel):
    directive_id: uuid.UUID
    prompt: str = Field(..., min_length=1, max_length=16_384)
    actor_id: str | None = Field(None, max_length=512)


class IdeChatResponse(BaseModel):
    reply: str
    correlation_id: uuid.UUID
    proof_object_id: uuid.UUID
