"""Validate router input context (100G) — same directive/task integrity as governed APIs."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import AgentRole
from app.models.task_ledger import TaskLedger


def validate_agent_role(raw: str) -> str:
    key = raw.strip().upper()
    try:
        return AgentRole(key).value
    except ValueError as e:
        raise ValueError("invalid_agent_role") from e


def resolve_router_context(
    session: Session,
    *,
    directive_id: uuid.UUID,
    task_id: uuid.UUID,
    agent_role: str,
    intent: str,
) -> tuple[Directive, TaskLedger, str]:
    if not intent.strip():
        raise ValueError("intent_required")

    role_val = validate_agent_role(agent_role)

    d = session.get(Directive, directive_id)
    if d is None:
        raise ValueError("directive_not_found")

    ledger = session.get(TaskLedger, task_id)
    if ledger is None:
        raise ValueError("task_not_found")
    if ledger.directive_id != directive_id:
        raise ValueError("task_directive_mismatch")

    return d, ledger, role_val
