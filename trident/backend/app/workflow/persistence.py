"""Persist task ledger, graph snapshot, and audits for LangGraph spine (100C)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit_clock import next_audit_created_at
from app.models.audit_event import AuditEvent
from app.models.directive import Directive
from app.models.enums import AgentRole, AuditActorType, AuditEventType, TaskLifecycleState
from app.models.graph_state import GraphState
from app.models.task_ledger import TaskLedger


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def append_graph_history(gs: GraphState, entry: dict[str, Any]) -> None:
    payload = dict(gs.state_payload_json or {})
    hist = list(payload.get("spine_history", []))
    hist.append(entry)
    payload["spine_history"] = hist
    gs.state_payload_json = payload
    gs.updated_at = _utcnow()


def record_node(
    session: Session,
    *,
    directive: Directive,
    ledger: TaskLedger,
    graph: GraphState,
    node: str,
    to_ledger: TaskLifecycleState,
    agent: AgentRole,
) -> None:
    now = _utcnow()
    fr = ledger.current_state
    ledger.current_state = to_ledger.value
    ledger.current_agent_role = agent.value
    ledger.last_transition_at = now
    ledger.updated_at = now

    graph.current_node = node
    append_graph_history(
        graph,
        {
            "node": node,
            "ledger": to_ledger.value,
            "at": now.isoformat(),
        },
    )
    session.flush()

    session.add(
        AuditEvent(
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
            event_type=AuditEventType.STATE_TRANSITION.value,
            event_payload_json={
                "node": node,
                "from_ledger": fr,
                "to_ledger": to_ledger.value,
                "agent": agent.value,
            },
            actor_type=AuditActorType.SYSTEM.value,
            actor_id=f"spine:{node}",
            created_at=next_audit_created_at(session),
        )
    )
    session.add(
        AuditEvent(
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
            event_type=AuditEventType.GRAPH_STATE_WRITTEN.value,
            event_payload_json={
                "node": node,
                "current_node": node,
                "graph_id": graph.graph_id,
            },
            actor_type=AuditActorType.SYSTEM.value,
            actor_id=f"spine:{node}",
            created_at=next_audit_created_at(session),
        )
    )


def update_directive_status(session: Session, directive: Directive, status: str) -> None:
    directive.status = status
    directive.updated_at = _utcnow()
    session.flush()


def load_spine_context(session: Session, directive_id: uuid.UUID) -> tuple[Directive, TaskLedger, GraphState] | None:
    d = session.get(Directive, directive_id)
    if d is None:
        return None
    ledger = session.scalar(select(TaskLedger).where(TaskLedger.directive_id == directive_id))
    if ledger is None:
        return None
    graph = session.scalar(select(GraphState).where(GraphState.directive_id == directive_id))
    if graph is None:
        return None
    return d, ledger, graph
