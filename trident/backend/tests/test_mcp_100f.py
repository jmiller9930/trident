"""MCP execution layer — simulated adapters, gates, receipts (100F)."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.enums import AgentRole, AuditEventType, ProofObjectType
from app.models.proof_object import ProofObject
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _directive_and_task(db_session: Session, ids: dict[str, uuid.UUID]) -> tuple[uuid.UUID, uuid.UUID]:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="MCP 100F test",
        graph_id="mcp-f",
        created_by_user_id=ids["user_id"],
    )
    d, ledger, _gs = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id, ledger.id


def _ctx(did: uuid.UUID, tid: uuid.UUID, *, command: str, target: str = "local") -> dict:
    return {
        "directive_id": str(did),
        "task_id": str(tid),
        "agent_role": AgentRole.ENGINEER.value,
        "command": command,
        "target": target,
    }


def test_mcp_classify_low_and_high(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did, tid = _directive_and_task(db_session, minimal_project_ids)
    low = client.post("/api/v1/mcp/classify", json=_ctx(did, tid, command="pytest tests/test_x.py"))
    assert low.status_code == 200
    assert low.json()["risk"] == "LOW"
    high = client.post("/api/v1/mcp/classify", json=_ctx(did, tid, command="trident_force_high noop"))
    assert high.status_code == 200
    assert high.json()["risk"] == "HIGH"


def test_mcp_execute_low_auto_no_explicit_approval_required(
    client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did, tid = _directive_and_task(db_session, minimal_project_ids)
    res = client.post(
        "/api/v1/mcp/execute",
        json={**_ctx(did, tid, command="pytest -q"), "explicitly_approved": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["risk"] == "LOW"
    assert body["simulated"] is True
    assert body["status"] == "success"
    assert "[simulated-local]" in body["stdout"]

    pid = uuid.UUID(body["proof_object_id"])
    proof = db_session.get(ProofObject, pid)
    assert proof is not None
    assert proof.proof_type == ProofObjectType.EXECUTION_LOG.value
    receipt = json.loads(proof.proof_summary or "{}")
    assert receipt["status"] == "success"
    assert receipt["simulated"] is True

    types = [
        r.event_type
        for r in db_session.scalars(select(AuditEvent).where(AuditEvent.directive_id == did)).all()
        if r.event_type
        in (
            AuditEventType.MCP_EXECUTION_REQUESTED.value,
            AuditEventType.MCP_EXECUTION_COMPLETED.value,
            AuditEventType.MCP_EXECUTION_REJECTED.value,
        )
    ]
    assert AuditEventType.MCP_EXECUTION_REQUESTED.value in types
    assert AuditEventType.MCP_EXECUTION_COMPLETED.value in types
    assert AuditEventType.MCP_EXECUTION_REJECTED.value not in types


def test_mcp_execute_high_rejected_without_explicit_approval(
    client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did, tid = _directive_and_task(db_session, minimal_project_ids)
    res = client.post(
        "/api/v1/mcp/execute",
        json={**_ctx(did, tid, command="trident_force_high dangerous"), "explicitly_approved": False},
    )
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["code"] == "high_risk_not_approved"
    pid = uuid.UUID(detail["proof_object_id"])

    proof = db_session.get(ProofObject, pid)
    assert proof is not None
    assert proof.proof_type == ProofObjectType.EXECUTION_LOG.value
    receipt = json.loads(proof.proof_summary or "{}")
    assert receipt["status"] == "rejected_high_unapproved"

    types = [
        r.event_type
        for r in db_session.scalars(select(AuditEvent).where(AuditEvent.directive_id == did)).all()
        if r.event_type
        in (
            AuditEventType.MCP_EXECUTION_REQUESTED.value,
            AuditEventType.MCP_EXECUTION_COMPLETED.value,
            AuditEventType.MCP_EXECUTION_REJECTED.value,
        )
    ]
    assert AuditEventType.MCP_EXECUTION_REQUESTED.value in types
    assert AuditEventType.MCP_EXECUTION_REJECTED.value in types
    assert AuditEventType.MCP_EXECUTION_COMPLETED.value not in types


def test_mcp_execute_high_passes_with_explicit_approval(
    client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did, tid = _directive_and_task(db_session, minimal_project_ids)
    res = client.post(
        "/api/v1/mcp/execute",
        json={**_ctx(did, tid, command="trident_force_high approved-run"), "explicitly_approved": True},
    )
    assert res.status_code == 200
    assert res.json()["risk"] == "HIGH"
    assert res.json()["explicitly_approved"] is True


def test_mcp_ssh_stub_adapter_simulated(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did, tid = _directive_and_task(db_session, minimal_project_ids)
    res = client.post(
        "/api/v1/mcp/execute",
        json={**_ctx(did, tid, command="pytest -q", target="ssh_stub"), "explicitly_approved": False},
    )
    assert res.status_code == 200
    assert res.json()["adapter"] == "ssh_stub"


def test_mcp_package_has_no_subprocess_execution_path() -> None:
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "mcp"
    text = ""
    for p in root.rglob("*.py"):
        text += p.read_text()
    assert "subprocess" not in text
    assert "os.system" not in text


def test_mcp_agent_role_case_insensitive(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did, tid = _directive_and_task(db_session, minimal_project_ids)
    res = client.post(
        "/api/v1/mcp/classify",
        json={
            "directive_id": str(did),
            "task_id": str(tid),
            "agent_role": "engineer",
            "command": "pytest",
            "target": "local",
        },
    )
    assert res.status_code == 200


def test_mcp_invalid_target(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did, tid = _directive_and_task(db_session, minimal_project_ids)
    res = client.post("/api/v1/mcp/classify", json=_ctx(did, tid, command="pytest", target="/bin/bash"))
    assert res.status_code == 400
    assert res.json()["detail"] == "invalid_target"
