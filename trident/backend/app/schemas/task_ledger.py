"""Pydantic schemas for task ledger (validation helpers)."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.enums import AgentRole, TaskLifecycleState


class TaskLedgerStatePayload(BaseModel):
    """Used for audit payloads — not persisted as separate row."""

    current_state: TaskLifecycleState
    current_agent_role: AgentRole
