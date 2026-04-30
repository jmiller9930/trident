"""Router API contracts (100G)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class RouterRouteRequest(BaseModel):
    directive_id: uuid.UUID
    task_id: uuid.UUID
    agent_role: str = Field(min_length=1, max_length=32)
    intent: str = Field(min_length=1, max_length=8192)
    payload: dict[str, Any] = Field(default_factory=dict)


class RouterRouteResponse(BaseModel):
    route: str | None = Field(default=None, description="MCP | LANGGRAPH | NIKE | MEMORY when validated")
    reason: str
    next_action: str = ""
    validated: bool
