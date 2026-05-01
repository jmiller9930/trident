"""Audit routing decisions (100R §9)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType
from app.models.task_ledger import TaskLedger
from app.repositories.audit_repository import AuditRepository


def log_routing_decision(
    session: Session,
    *,
    directive: Directive,
    ledger: TaskLedger,
    payload: dict[str, Any],
) -> None:
    AuditRepository(session).record(
        event_type=AuditEventType.MODEL_ROUTING_DECISION,
        event_payload=payload,
        actor_type=AuditActorType.SYSTEM,
        actor_id="trident-model-router",
        workspace_id=directive.workspace_id,
        project_id=directive.project_id,
        directive_id=directive.id,
    )


def log_budget_warning(
    session: Session,
    *,
    directive: Directive,
    ledger: TaskLedger,
    payload: dict[str, Any],
) -> None:
    AuditRepository(session).record(
        event_type=AuditEventType.MODEL_ROUTING_BUDGET_WARNING,
        event_payload=payload,
        actor_type=AuditActorType.SYSTEM,
        actor_id="trident-model-router:budget",
        workspace_id=directive.workspace_id,
        project_id=directive.project_id,
        directive_id=directive.id,
    )


def log_benchmark_hook(
    session: Session,
    *,
    directive: Directive,
    ledger: TaskLedger,
    metrics: dict[str, Any],
) -> None:
    """Health/benchmark placeholder — auditable, no IDE/MCP/Nike coupling."""
    AuditRepository(session).record(
        event_type=AuditEventType.MODEL_ROUTER_BENCHMARK,
        event_payload={
            "task_id": str(ledger.id),
            "directive_id": str(directive.id),
            **metrics,
        },
        actor_type=AuditActorType.SYSTEM,
        actor_id="trident-model-router:benchmark",
        workspace_id=directive.workspace_id,
        project_id=directive.project_id,
        directive_id=directive.id,
    )
