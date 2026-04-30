"""Agent execution layer — governed LangGraph → MCP → memory path (100H)."""

from __future__ import annotations

import pathlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.memory_entry import MemoryEntry
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.workflow.spine import run_spine_workflow


def _create_directive(session: Session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="100H agent test",
        graph_id="spine-100h",
        created_by_user_id=ids["user_id"],
    )
    d, _l, _g = DirectiveRepository(session).create_directive_and_initialize(body)
    session.commit()
    return d.id


def _agent_audit_ordered_subsequence_present(rows: list[AuditEvent]) -> bool:
    types = [r.event_type for r in rows]
    want = (
        AuditEventType.AGENT_INVOCATION.value,
        AuditEventType.AGENT_DECISION.value,
        AuditEventType.AGENT_MCP_REQUEST.value,
        AuditEventType.MCP_EXECUTION_REQUESTED.value,
        AuditEventType.MCP_EXECUTION_COMPLETED.value,
        AuditEventType.MEMORY_WRITE.value,
        AuditEventType.AGENT_RESULT.value,
    )
    j = 0
    for t in types:
        if j < len(want) and t == want[j]:
            j += 1
    return j == len(want)


def test_engineer_agent_emits_governed_audit_chain(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    run_spine_workflow(db_session, did, reviewer_rejections_remaining=0)
    db_session.commit()

    rows = db_session.scalars(
        select(AuditEvent).where(AuditEvent.directive_id == did).order_by(AuditEvent.created_at.asc())
    ).all()
    assert _agent_audit_ordered_subsequence_present(rows), "expected ordered AGENT→MCP→MEMORY_WRITE→AGENT_RESULT subsequence"


def test_engineer_writes_agent_memory_title(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    run_spine_workflow(db_session, did, reviewer_rejections_remaining=0)
    db_session.commit()

    titles = db_session.scalars(select(MemoryEntry.title).where(MemoryEntry.directive_id == did)).all()
    assert any(t and str(t).startswith("agent:engineer") for t in titles)


def test_agents_package_has_no_subprocess_or_shell() -> None:
    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "agents"
    text = ""
    for p in root.rglob("*.py"):
        text += p.read_text()
    assert "subprocess" not in text
    assert "os.system" not in text
