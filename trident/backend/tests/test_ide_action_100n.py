"""100N — orchestrated IDE action endpoint."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _directive(client: TestClient, db_session, ids: dict[str, uuid.UUID]) -> tuple[uuid.UUID, uuid.UUID]:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="100N IDE action",
        graph_id="100n-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id, ids["project_id"]


def _action(project_id: uuid.UUID, directive_id: uuid.UUID, **kwargs) -> dict:
    base = {
        "project_id": str(project_id),
        "directive_id": str(directive_id),
        "agent_role": "ENGINEER",
        "actor_id": "pytest",
    }
    base.update(kwargs)
    return base


def test_ide_action_ask_requires_prompt(client: TestClient, db_session, minimal_project_ids) -> None:
    did, pid = _directive(client, db_session, minimal_project_ids)
    r = client.post("/api/v1/ide/action", json=_action(pid, did, action="ASK", prompt=""))
    assert r.status_code == 422


def test_ide_action_project_mismatch(client: TestClient, db_session, minimal_project_ids) -> None:
    did, _pid = _directive(client, db_session, minimal_project_ids)
    wrong = uuid.uuid4()
    r = client.post(
        "/api/v1/ide/action",
        json=_action(wrong, did, action="ASK", prompt="hello"),
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "directive_project_mismatch"


def test_ide_action_ask_orchestrated(client: TestClient, db_session, minimal_project_ids) -> None:
    did, pid = _directive(client, db_session, minimal_project_ids)
    r = client.post(
        "/api/v1/ide/action",
        json=_action(pid, did, action="ASK", prompt="workflow_progress question"),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["action"] == "ASK"
    assert data["correlation_id"]
    assert data["directive_status"]
    assert data["task_ledger_state"]
    assert data["current_agent_role"]
    assert "deterministic stub" in (data["reply"] or "")
    assert data["proof_object_id"]
    assert data["router"] is not None
    assert "validated" in data["router"]
    assert data["memory_preview"] is not None
    assert data["mcp_recent"] is not None

    orch = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.event_type == AuditEventType.IDE_ORCHESTRATED_ACTION.value,
            AuditEvent.directive_id == did,
        )
    )
    assert int(orch or 0) >= 1


def test_ide_action_run_workflow(client: TestClient, db_session, minimal_project_ids) -> None:
    did, pid = _directive(client, db_session, minimal_project_ids)
    r = client.post(
        "/api/v1/ide/action",
        json=_action(pid, did, action="RUN_WORKFLOW", reviewer_rejections_remaining=0),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["action"] == "RUN_WORKFLOW"
    assert data["correlation_id"]
    assert data["nodes_executed"]
    assert len(data["nodes_executed"]) >= 1
    assert data["router"] is not None


def test_ide_action_propose_patch(client: TestClient, db_session, minimal_project_ids) -> None:
    did, pid = _directive(client, db_session, minimal_project_ids)
    r = client.post(
        "/api/v1/ide/action",
        json=_action(pid, did, action="PROPOSE_PATCH", prompt="change foo"),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["patch_guidance"]
    assert "Patch workflow" in data["patch_guidance"]
    assert data["proof_object_id"]
    assert data["router"] is not None


def test_ide_action_chat_correlation_passthrough(client: TestClient, db_session, minimal_project_ids) -> None:
    """ASK uses one correlation_id for stub reply + orchestration envelope."""
    did, pid = _directive(client, db_session, minimal_project_ids)
    r = client.post(
        "/api/v1/ide/action",
        json=_action(pid, did, action="ASK", prompt="ping"),
    )
    assert r.status_code == 200
    cid = r.json()["correlation_id"]
    assert cid in r.json()["reply"]
