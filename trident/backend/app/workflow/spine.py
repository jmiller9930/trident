"""
LangGraph workflow spine — Architect → Engineer → Reviewer → Docs → Close with reviewer rejection loop.

All lifecycle mutations go through this graph per directive 100C; nodes are nested callables
(not exported) so execution outside `compile_spine(...).invoke()` is structurally discouraged.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.memory.constants import MemoryKind
from app.memory.memory_writer import MemoryWriter
from app.models.enums import AgentRole, DirectiveStatus, TaskLifecycleState
from app.models.directive import Directive
from app.models.task_ledger import TaskLedger
from app.agents.agent_executor import run_engineer_agent_phase
from app.workflow.persistence import load_spine_context, record_node, update_directive_status
from app.workflow.state import SpineState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _spine_memory_checkpoint(session: Session, state: SpineState, directive: Directive, ledger: TaskLedger, node: str) -> None:
    MemoryWriter(session).write_from_graph(
        directive_id=directive.id,
        task_ledger_id=ledger.id,
        agent_role=ledger.current_agent_role,
        workflow_run_nonce=state["workflow_run_nonce"],
        title=f"spine:{node}",
        body=f"Graph checkpoint after spine node {node} (directive {directive.id})",
        memory_kind=MemoryKind.STRUCTURED.value,
    )


def compile_spine(session: Session):
    """Return a compiled graph that closes over `session` (one compile per request)."""

    def architect(state: SpineState) -> dict[str, Any]:
        did = uuid.UUID(state["directive_id"])
        ctx = load_spine_context(session, did)
        if ctx is None:
            raise ValueError("directive_not_found")
        directive, ledger, graph = ctx
        update_directive_status(session, directive, DirectiveStatus.ACTIVE.value)
        record_node(
            session,
            directive=directive,
            ledger=ledger,
            graph=graph,
            node="architect",
            to_ledger=TaskLifecycleState.APPROVED,
            agent=AgentRole.ARCHITECT,
        )
        _spine_memory_checkpoint(session, state, directive, ledger, "architect")
        return {"nodes_executed": ["architect"]}

    def engineer(state: SpineState) -> dict[str, Any]:
        did = uuid.UUID(state["directive_id"])
        ctx = load_spine_context(session, did)
        if ctx is None:
            raise ValueError("directive_not_found")
        directive, ledger, graph = ctx
        update_directive_status(session, directive, DirectiveStatus.IN_PROGRESS.value)
        record_node(
            session,
            directive=directive,
            ledger=ledger,
            graph=graph,
            node="engineer",
            to_ledger=TaskLifecycleState.IN_PROGRESS,
            agent=AgentRole.ENGINEER,
        )
        out = run_engineer_agent_phase(session, directive, ledger, graph, state)
        if out.memory_write is None:
            _spine_memory_checkpoint(session, state, directive, ledger, "engineer")
        return {"nodes_executed": ["engineer"]}

    def reviewer(state: SpineState) -> dict[str, Any]:
        did = uuid.UUID(state["directive_id"])
        ctx = load_spine_context(session, did)
        if ctx is None:
            raise ValueError("directive_not_found")
        directive, ledger, graph = ctx
        rem = int(state["reviewer_rejections_remaining"])
        update_directive_status(session, directive, DirectiveStatus.REVIEW.value)
        record_node(
            session,
            directive=directive,
            ledger=ledger,
            graph=graph,
            node="reviewer",
            to_ledger=TaskLifecycleState.REVIEW,
            agent=AgentRole.REVIEWER,
        )
        if rem > 0:
            record_node(
                session,
                directive=directive,
                ledger=ledger,
                graph=graph,
                node="reviewer_reject",
                to_ledger=TaskLifecycleState.REJECTED,
                agent=AgentRole.REVIEWER,
            )
            _spine_memory_checkpoint(session, state, directive, ledger, "reviewer")
            return {
                "reviewer_rejections_remaining": rem - 1,
                "reviewer_send_back": True,
                "nodes_executed": ["reviewer"],
            }
        _spine_memory_checkpoint(session, state, directive, ledger, "reviewer")
        return {"reviewer_send_back": False, "nodes_executed": ["reviewer"]}

    def documentation(state: SpineState) -> dict[str, Any]:
        did = uuid.UUID(state["directive_id"])
        ctx = load_spine_context(session, did)
        if ctx is None:
            raise ValueError("directive_not_found")
        directive, ledger, graph = ctx
        record_node(
            session,
            directive=directive,
            ledger=ledger,
            graph=graph,
            node="documentation",
            to_ledger=TaskLifecycleState.REVIEW,
            agent=AgentRole.DOCUMENTATION,
        )
        _spine_memory_checkpoint(session, state, directive, ledger, "documentation")
        return {"nodes_executed": ["documentation"]}

    def close(state: SpineState) -> dict[str, Any]:
        did = uuid.UUID(state["directive_id"])
        ctx = load_spine_context(session, did)
        if ctx is None:
            raise ValueError("directive_not_found")
        directive, ledger, graph = ctx
        update_directive_status(session, directive, DirectiveStatus.COMPLETE.value)
        # Memory write before terminal ledger transition (validator rejects CLOSED).
        _spine_memory_checkpoint(session, state, directive, ledger, "pre_close")
        record_node(
            session,
            directive=directive,
            ledger=ledger,
            graph=graph,
            node="close",
            to_ledger=TaskLifecycleState.CLOSED,
            agent=AgentRole.SYSTEM,
        )
        return {"nodes_executed": ["close"]}

    def route_reviewer(s: SpineState) -> str:
        return "engineer" if s.get("reviewer_send_back") else "documentation"

    g = StateGraph(SpineState)
    g.add_node("architect", architect)
    g.add_node("engineer", engineer)
    g.add_node("reviewer", reviewer)
    g.add_node("documentation", documentation)
    g.add_node("close", close)

    g.add_edge(START, "architect")
    g.add_edge("architect", "engineer")
    g.add_edge("engineer", "reviewer")
    g.add_conditional_edges(
        "reviewer",
        route_reviewer,
        {"engineer": "engineer", "documentation": "documentation"},
    )
    g.add_edge("documentation", "close")
    g.add_edge("close", END)

    return g.compile()


def run_spine_workflow(
    session: Session,
    directive_id: uuid.UUID,
    *,
    reviewer_rejections_remaining: int = 0,
) -> SpineState:
    """Single supported entrypoint for graph execution (100C bypass guard)."""
    ctx = load_spine_context(session, directive_id)
    if ctx is None:
        raise ValueError("directive_not_found")
    _d, ledger, gs = ctx
    if ledger.current_state == TaskLifecycleState.CLOSED.value:
        raise ValueError("workflow_already_complete")

    nonce = str(uuid.uuid4())
    payload = dict(gs.state_payload_json or {})
    payload["workflow_run_nonce"] = nonce
    gs.state_payload_json = payload
    gs.updated_at = _utcnow()
    session.flush()

    graph = compile_spine(session)
    try:
        return graph.invoke(
            {
                "directive_id": str(directive_id),
                "workflow_run_nonce": nonce,
                "reviewer_rejections_remaining": reviewer_rejections_remaining,
                "reviewer_send_back": False,
                "nodes_executed": [],
            }
        )
    finally:
        ctx2 = load_spine_context(session, directive_id)
        if ctx2:
            _d2, _l2, gs2 = ctx2
            p2 = dict(gs2.state_payload_json or {})
            p2.pop("workflow_run_nonce", None)
            gs2.state_payload_json = p2
            gs2.updated_at = _utcnow()
            session.flush()
