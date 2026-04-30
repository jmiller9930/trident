"""Structured agent outputs — MCP and memory fields are advisory; executor enforces paths."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class AgentDecisionStatus(StrEnum):
    CONTINUE = "CONTINUE"
    COMPLETE = "COMPLETE"
    BLOCKED = "BLOCKED"


class AgentMCPIntent(BaseModel):
    command: str = Field(min_length=1, max_length=8192)
    target: str = Field(default="local", min_length=1, max_length=64)
    explicitly_approved: bool = False


class AgentMemoryWriteIntent(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    body: str = Field(min_length=1)
    memory_kind: str = Field(min_length=1, max_length=64)


class AgentOutput(BaseModel):
    decision: str = Field(min_length=1)
    status: AgentDecisionStatus
    mcp_request: AgentMCPIntent | None = None
    memory_write: AgentMemoryWriteIntent | None = None
