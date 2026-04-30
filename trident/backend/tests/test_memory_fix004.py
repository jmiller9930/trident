"""FIX 004 — memory consistency, vector lifecycle, retrieval freshness."""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.graph_state import GraphState
from app.models.memory_entry import MemoryEntry
from app.models.task_ledger import TaskLedger
from app.memory.constants import MemoryVectorState
from app.memory.vector_service import VectorMemoryService
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _create_directive(session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="FIX004 directive",
        graph_id="fix004-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(session).create_directive_and_initialize(body)
    session.commit()
    return d.id


def test_monotonic_memory_sequence_on_writes(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    ledger = db_session.scalar(select(TaskLedger).where(TaskLedger.directive_id == did))
    graph = db_session.scalar(select(GraphState).where(GraphState.directive_id == did))
    assert ledger and graph
    nonce = str(uuid.uuid4())
    payload = dict(graph.state_payload_json or {})
    payload["workflow_run_nonce"] = nonce
    graph.state_payload_json = payload
    db_session.commit()

    seqs: list[int] = []
    for i in range(3):
        r = client.post(
            "/api/v1/memory/write",
            json={
                "directive_id": str(did),
                "task_id": str(ledger.id),
                "agent_role": ledger.current_agent_role,
                "workflow_context_marker": nonce,
                "memory_kind": "OBSERVATION",
                "body": f"seq proof {i} banana apple",
            },
        )
        assert r.status_code == 200, r.text
        seqs.append(int(r.json()["memory_sequence"]))
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == 3


def test_vector_index_failure_preserves_structured_row_and_audits(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        VectorMemoryService,
        "upsert_document",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("chroma_simulated_down")),
    )

    did = _create_directive(db_session, minimal_project_ids)
    ledger = db_session.scalar(select(TaskLedger).where(TaskLedger.directive_id == did))
    graph = db_session.scalar(select(GraphState).where(GraphState.directive_id == did))
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
            "memory_kind": "OBSERVATION",
            "body": "structured survives chroma failure",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["vector_state"] == MemoryVectorState.VECTOR_FAILED.value
    assert data["chroma_document_id"] is None

    mid = uuid.UUID(data["memory_entry_id"])
    row = db_session.get(MemoryEntry, mid)
    assert row is not None
    assert row.body_text == "structured survives chroma failure"
    assert row.memory_sequence == data["memory_sequence"]

    n_fail = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.event_type == AuditEventType.MEMORY_VECTOR_INDEX_FAILED.value
        )
    )
    assert int(n_fail or 0) >= 1
    n_write = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.MEMORY_WRITE.value)
    )
    assert int(n_write or 0) >= 1


def test_retry_vector_index_recovers_after_initial_failure(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}
    orig = VectorMemoryService.upsert_document

    def flaky(self, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("temporary chroma outage")
        return orig(self, *a, **k)

    monkeypatch.setattr(VectorMemoryService, "upsert_document", flaky)

    did = _create_directive(db_session, minimal_project_ids)
    ledger = db_session.scalar(select(TaskLedger).where(TaskLedger.directive_id == did))
    graph = db_session.scalar(select(GraphState).where(GraphState.directive_id == did))
    nonce = str(uuid.uuid4())
    payload = dict(graph.state_payload_json or {})
    payload["workflow_run_nonce"] = nonce
    graph.state_payload_json = payload
    db_session.commit()

    r1 = client.post(
        "/api/v1/memory/write",
        json={
            "directive_id": str(did),
            "task_id": str(ledger.id),
            "agent_role": ledger.current_agent_role,
            "workflow_context_marker": nonce,
            "memory_kind": "OBSERVATION",
            "body": "retry recovery phrase zzyyxx unique",
        },
    )
    assert r1.status_code == 200
    assert r1.json()["vector_state"] == MemoryVectorState.VECTOR_FAILED.value
    mid = r1.json()["memory_entry_id"]

    r2 = client.post(
        "/api/v1/memory/retry-vector-index",
        json={
            "directive_id": str(did),
            "task_id": str(ledger.id),
            "agent_role": ledger.current_agent_role,
            "workflow_context_marker": nonce,
            "memory_entry_id": mid,
        },
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["vector_state"] == MemoryVectorState.VECTOR_INDEXED.value
    assert r2.json()["chroma_document_id"] == mid

    ok = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.event_type == AuditEventType.MEMORY_VECTOR_REINDEX_SUCCESS.value
        )
    )
    assert int(ok or 0) >= 1


def test_directive_memory_ordered_deterministically(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    ledger = db_session.scalar(select(TaskLedger).where(TaskLedger.directive_id == did))
    graph = db_session.scalar(select(GraphState).where(GraphState.directive_id == did))
    nonce = str(uuid.uuid4())
    payload = dict(graph.state_payload_json or {})
    payload["workflow_run_nonce"] = nonce
    graph.state_payload_json = payload
    db_session.commit()

    for i in range(2):
        r = client.post(
            "/api/v1/memory/write",
            json={
                "directive_id": str(did),
                "task_id": str(ledger.id),
                "agent_role": ledger.current_agent_role,
                "workflow_context_marker": nonce,
                "memory_kind": "OBSERVATION",
                "body": f"order token {i}",
            },
        )
        assert r.status_code == 200

    r = client.get(f"/api/v1/memory/directive/{did}")
    assert r.status_code == 200
    body = r.json()
    entries = body["memory_entries"]
    seqs = [e["memory_sequence"] for e in entries]
    assert seqs == sorted(seqs)
    assert body["memory_read_policy"]["ordering"] == "memory_sequence_asc"


def test_vector_retrieval_freshness_marks_stale_untrusted(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    ledger = db_session.scalar(select(TaskLedger).where(TaskLedger.directive_id == did))
    graph = db_session.scalar(select(GraphState).where(GraphState.directive_id == did))
    nonce = str(uuid.uuid4())
    payload = dict(graph.state_payload_json or {})
    payload["workflow_run_nonce"] = nonce
    graph.state_payload_json = payload
    db_session.commit()

    unique = "stalefreshnessmarker98765"
    r = client.post(
        "/api/v1/memory/write",
        json={
            "directive_id": str(did),
            "task_id": str(ledger.id),
            "agent_role": ledger.current_agent_role,
            "workflow_context_marker": nonce,
            "memory_kind": "OBSERVATION",
            "body": f"indexed body {unique}",
        },
    )
    assert r.status_code == 200
    mid = uuid.UUID(r.json()["memory_entry_id"])

    db_session.execute(
        update(MemoryEntry).where(MemoryEntry.id == mid).values(vector_state=MemoryVectorState.VECTOR_STALE.value)
    )
    db_session.commit()

    r2 = client.get(f"/api/v1/memory/directive/{did}", params={"q": unique, "top_k": 8})
    assert r2.status_code == 200
    vr = r2.json().get("vector_retrieval")
    assert vr is not None
    assert vr["freshness"] in (
        "vector_untrusted_use_structured_list",
        "vector_empty_use_structured_list",
    )
    assert vr["trusted_hit_count"] == 0
    if vr["hit_count"]:
        assert any(not h["vector_hit_trusted"] for h in vr["hits"])
