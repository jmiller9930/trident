"""Memory system — directive 100D."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config.settings import Settings
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.graph_state import GraphState
from app.models.memory_entry import MemoryEntry
from app.models.task_ledger import TaskLedger
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.workflow.spine import run_spine_workflow

from app.memory.constants import MemoryKind
from app.memory.vector_service import VectorMemoryService


def _create_directive(session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Memory test directive",
        graph_id="mem-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(session).create_directive_and_initialize(body)
    session.commit()
    return d.id


def test_guarded_memory_write_rejects_invalid_nonce(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    ledger = db_session.scalar(select(TaskLedger).where(TaskLedger.directive_id == did))
    graph = db_session.scalar(select(GraphState).where(GraphState.directive_id == did))
    assert ledger is not None and graph is not None
    payload = dict(graph.state_payload_json or {})
    payload["workflow_run_nonce"] = str(uuid.uuid4())
    graph.state_payload_json = payload
    db_session.commit()

    r = client.post(
        "/api/v1/memory/write",
        json={
            "directive_id": str(did),
            "task_id": str(ledger.id),
            "agent_role": ledger.current_agent_role,
            "workflow_context_marker": str(uuid.uuid4()),
            "memory_kind": MemoryKind.OBSERVATION.value,
            "body": "should fail",
        },
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "invalid_workflow_context_marker"


def test_guarded_memory_write_accepts_matching_nonce(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    ledger = db_session.scalar(select(TaskLedger).where(TaskLedger.directive_id == did))
    graph = db_session.scalar(select(GraphState).where(GraphState.directive_id == did))
    assert ledger is not None and graph is not None
    nonce = str(uuid.uuid4())
    payload = dict(graph.state_payload_json or {})
    payload["workflow_run_nonce"] = nonce
    graph.state_payload_json = payload
    db_session.commit()

    r = client.post(
        "/api/v1/memory/write",
        json={
            "directive_id": str(did),
            "task_id": str(ledger.id),
            "agent_role": ledger.current_agent_role,
            "workflow_context_marker": nonce,
            "memory_kind": MemoryKind.OBSERVATION.value,
            "title": "rest guarded",
            "body": "accepted write",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["chroma_document_id"]


def test_spine_run_creates_memory_entries(db_session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    run_spine_workflow(db_session, did, reviewer_rejections_remaining=0)
    db_session.commit()
    n = db_session.scalar(select(func.count()).select_from(MemoryEntry).where(MemoryEntry.directive_id == did)) or 0
    assert int(n) >= 5


def test_directive_memory_read_emits_audit(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    before = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.MEMORY_READ_ACCESS.value)
    ) or 0
    r = client.get(f"/api/v1/memory/directive/{did}")
    assert r.status_code == 200
    after = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.MEMORY_READ_ACCESS.value)
    ) or 0
    assert int(after) == int(before) + 1


def test_chroma_persistence_restart_same_path(tmp_path) -> None:
    """Restart proof: second client on same PersistentClient path sees prior vectors."""
    path = str(tmp_path / "chroma_store")
    cfg = Settings(chroma_host="", chroma_local_path=path)
    v1 = VectorMemoryService(cfg)
    v1.upsert_document(
        doc_id="doc-proof-1",
        document="persistence proof phrase alpha beta",
        project_id="proj-a",
        directive_id="dir-a",
        memory_kind="STRUCTURED",
    )
    v2 = VectorMemoryService(cfg)
    out = v2.query_similar("alpha beta phrase", project_id="proj-a", directive_id="dir-a", top_k=5)
    assert len(out["ids"]) >= 1
    assert "doc-proof-1" in out["ids"]
