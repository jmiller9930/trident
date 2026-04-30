"""100K — IDE chat deterministic stub + audit + CHAT_LOG proof."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType, ProofObjectType
from app.models.proof_object import ProofObject
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _directive_id(session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="IDE chat test",
        graph_id="ide-chat-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(session).create_directive_and_initialize(body)
    session.commit()
    return d.id


def test_ide_chat_stub_writes_audits_and_proof(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did = _directive_id(db_session, minimal_project_ids)
    r = client.post(
        "/api/v1/ide/chat",
        json={"directive_id": str(did), "prompt": "hello from ide", "actor_id": "vscode-test"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "reply" in data and "correlation_id" in data and "proof_object_id" in data
    assert "deterministic stub" in data["reply"]
    pid = uuid.UUID(data["proof_object_id"])

    proof = db_session.get(ProofObject, pid)
    assert proof is not None
    assert proof.proof_type == ProofObjectType.CHAT_LOG.value
    assert proof.directive_id == did
    summary = json.loads(proof.proof_summary or "{}")
    assert summary.get("schema") == "ide_chat_stub_v1"
    assert "prompt_sha256" in summary and "reply_sha256" in summary

    evs = list(
        db_session.scalars(
            select(AuditEvent).where(AuditEvent.directive_id == did).order_by(AuditEvent.created_at.asc())
        ).all()
    )
    types = [e.event_type for e in evs]
    assert AuditEventType.IDE_CHAT_REQUEST.value in types
    assert AuditEventType.IDE_CHAT_RESPONSE.value in types
    req = next(e for e in evs if e.event_type == AuditEventType.IDE_CHAT_REQUEST.value)
    assert req.event_payload_json.get("prompt_length") == len("hello from ide")
    assert req.actor_type == "USER"


def test_ide_chat_unknown_directive(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    _ = _directive_id(db_session, minimal_project_ids)
    missing = uuid.uuid4()
    r = client.post(
        "/api/v1/ide/chat",
        json={"directive_id": str(missing), "prompt": "x"},
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "directive_not_found"
