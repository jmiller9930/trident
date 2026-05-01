"""Read-only context passed into agent handlers (100H)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.models.enums import AgentRole


@dataclass(frozen=True)
class AgentGraphContext:
    directive_id: uuid.UUID
    task_ledger_id: uuid.UUID
    workflow_run_nonce: str
    agent_role: AgentRole
    node_name: str
    memory_snapshot: dict[str, Any]
    model_routing: dict[str, Any] | None = None
