from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProofObjectRecord(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    directive_id: uuid.UUID
    proof_type: str = Field(max_length=64)
    proof_uri: str | None
    proof_summary: str | None
    proof_hash: str | None
    created_by_agent_role: str = Field(max_length=32)
    created_at: datetime
