"""Request/response contracts for MCP HTTP API (100F)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class MCPContextMixin(BaseModel):
    directive_id: uuid.UUID
    task_id: uuid.UUID
    agent_role: str = Field(min_length=1, max_length=32)
    command: str = Field(min_length=1, max_length=8192)
    target: str = Field(min_length=1, max_length=64)


class MCPClassifyRequest(MCPContextMixin):
    """Classification-only — same identity fields as execute (no anonymous intent)."""


class MCPClassifyResponse(BaseModel):
    risk: str
    classification_rationale: str


class MCPExecuteRequest(MCPContextMixin):
    """Simulated execution path — HIGH requires explicit approval."""

    explicitly_approved: bool = False


class MCPExecuteResponse(BaseModel):
    proof_object_id: uuid.UUID
    risk: str
    simulated: bool = True
    status: str
    explicitly_approved: bool
    adapter: str
    stdout: str
    stderr: str
    exit_code: int
