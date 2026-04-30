"""Subsystem router — pure decision layer (100G)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _did_tid(db_session: Session, ids: dict[str, uuid.UUID]) -> tuple[uuid.UUID, uuid.UUID]:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Router 100G",
        graph_id="r100g",
        created_by_user_id=ids["user_id"],
    )
    d, ledger, _gs = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id, ledger.id


def _body(did: uuid.UUID, tid: uuid.UUID, *, intent: str) -> dict:
    return {
        "directive_id": str(did),
        "task_id": str(tid),
        "agent_role": "engineer",
        "intent": intent,
        "payload": {},
    }


def test_router_matrix_explicit_prefixes(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did, tid = _did_tid(db_session, minimal_project_ids)
    for intent, exp in [
        ("route.memory", "MEMORY"),
        ("route.mcp", "MCP"),
        ("route.langgraph", "LANGGRAPH"),
        ("route.nike", "NIKE"),
    ]:
        r = client.post("/api/v1/router/route", json=_body(did, tid, intent=intent))
        assert r.status_code == 200
        j = r.json()
        assert j["validated"] is True
        assert j["route"] == exp
        assert j["next_action"]


def test_router_matrix_keywords(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did, tid = _did_tid(db_session, minimal_project_ids)
    matrix = [
        ("please_memory_read_context", "MEMORY"),
        ("need_mcp_execute_step", "MCP"),
        ("workflow_progress_review", "LANGGRAPH"),
        ("nike_dispatch_payload", "NIKE"),
    ]
    for intent, exp in matrix:
        r = client.post("/api/v1/router/route", json=_body(did, tid, intent=intent))
        assert r.status_code == 200
        j = r.json()
        assert j["validated"] is True, intent
        assert j["route"] == exp


def test_router_ambiguous_fail_closed(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did, tid = _did_tid(db_session, minimal_project_ids)
    # triggers both MCP and MEMORY keyword families
    r = client.post(
        "/api/v1/router/route",
        json=_body(did, tid, intent="mcp_execute_for_memory_read_recovery"),
    )
    assert r.status_code == 200
    j = r.json()
    assert j["validated"] is False
    assert j["route"] is None
    assert "ambiguous" in j["reason"] or j["reason"] == "ambiguous_multi_subsystem"


def test_router_unknown_intent_fail_closed(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did, tid = _did_tid(db_session, minimal_project_ids)
    r = client.post("/api/v1/router/route", json=_body(did, tid, intent="hello_world_unmatched"))
    assert r.status_code == 200
    j = r.json()
    assert j["validated"] is False
    assert j["route"] is None


def test_router_audit_router_decision_made(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did, tid = _did_tid(db_session, minimal_project_ids)
    before = len(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.directive_id == did,
                AuditEvent.event_type == AuditEventType.ROUTER_DECISION_MADE.value,
            )
        ).all()
    )
    client.post("/api/v1/router/route", json=_body(did, tid, intent="route.mcp"))
    after = db_session.scalars(
        select(AuditEvent).where(
            AuditEvent.directive_id == did,
            AuditEvent.event_type == AuditEventType.ROUTER_DECISION_MADE.value,
        )
    ).all()
    assert len(after) == before + 1
    payload = after[-1].event_payload_json
    assert payload.get("validated") is True
    assert payload.get("route") == "MCP"


def test_router_package_pure_decision_layer() -> None:
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "router"
    text = ""
    for p in root.rglob("*.py"):
        text += p.read_text()
    assert "subprocess" not in text
    assert "os.system" not in text

def test_router_has_no_execution_adapter_imports() -> None:
    """Router must not import MCP service, workflow runner, or Nike API modules."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "router"
    banned_substrings = (
        "app.mcp.mcp_service",
        "app.workflow.spine",
        "run_spine_workflow",
        "app.api.v1.nike",
    )
    for p in root.rglob("*.py"):
        src = p.read_text()
        for b in banned_substrings:
            assert b not in src, f"{p} must not reference {b}"
