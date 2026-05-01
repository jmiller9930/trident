"""TRIDENT_IMPLEMENTATION_DIRECTIVE_VALIDATION_001 — post-commit validation tracking."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.proof_object import ProofObject
from app.models.validation_run import ValidationRun, ValidationRunType, ValidationStatus
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _login(client, ids) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(ids) -> str:
    return str(ids["project_id"])


def _make_directive(db_session, ids) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Validate patch results",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


def _make_viewer(db_session, ids):
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    email = f"viewer-val-{uid}@example.com"
    u = User(id=uid, display_name="V", email=email, role="m",
             password_hash=hash_password("viewerpass!"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(
        project_id=ids["project_id"], user_id=uid, role=ProjectMemberRole.VIEWER.value
    ))
    db_session.commit()
    return {"email": email, "password": "viewerpass!"}


def _val_url(ids, did, vid=None, action=None) -> str:
    pid = _pid(ids)
    base = f"/api/v1/projects/{pid}/directives/{did}/validations"
    if vid is None:
        return base
    url = f"{base}/{vid}"
    return f"{url}/{action}" if action else url


_CREATE_BODY = {
    "validation_type": "MANUAL",
    "commit_sha": "abc123def456abc123def456abc123def456abc1",
    "result_summary": None,
}


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_validation_requires_auth(client, minimal_project_ids, db_session) -> None:
    did = _make_directive(db_session, minimal_project_ids)
    r = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY)
    assert r.status_code == 401


def test_viewer_cannot_create_validation(client, minimal_project_ids, db_session) -> None:
    viewer = _make_viewer(db_session, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    lr = client.post("/api/v1/auth/login", json=viewer)
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=vh)
    assert r.status_code == 403


def test_create_validation_returns_pending(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    r = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == ValidationStatus.PENDING.value
    assert body["validation_type"] == "MANUAL"
    assert body["commit_sha"] == _CREATE_BODY["commit_sha"]


def test_create_validation_persists_to_db(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    r = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = uuid.UUID(r.json()["id"])
    db_session.expire_all()
    row = db_session.get(ValidationRun, vid)
    assert row is not None
    assert row.status == ValidationStatus.PENDING.value


def test_create_validation_emits_audit(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.VALIDATION_CREATED.value)
    ).first()
    assert row is not None
    assert row.event_payload_json["validation_type"] == "MANUAL"


def test_create_validation_directive_mismatch_rejected(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    wrong_did = str(uuid.uuid4())
    r = client.post(_val_url(minimal_project_ids, wrong_did), json=_CREATE_BODY, headers=h)
    assert r.status_code == 422
    assert "directive_not_in_project" in r.json()["detail"]


def test_create_validation_patch_mismatch_rejected(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = {**_CREATE_BODY, "patch_id": str(uuid.uuid4())}
    r = client.post(_val_url(minimal_project_ids, did), json=body, headers=h)
    assert r.status_code == 422
    assert "patch_not_in_directive" in r.json()["detail"]


# ── List / get ────────────────────────────────────────────────────────────────

def test_list_validations(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    client.post(_val_url(minimal_project_ids, did),
                json={**_CREATE_BODY, "validation_type": "SMOKE"}, headers=h)
    r = client.get(_val_url(minimal_project_ids, did), headers=h)
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 2


def test_get_validation_returns_detail(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    r = client.get(_val_url(minimal_project_ids, did, vid), headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == vid


def test_get_validation_404_for_unknown(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    r = client.get(_val_url(minimal_project_ids, did, str(uuid.uuid4())), headers=h)
    assert r.status_code == 404


# ── Start ─────────────────────────────────────────────────────────────────────

def test_start_validation_transitions_to_running(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    r = client.post(_val_url(minimal_project_ids, did, vid, "start"), headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == ValidationStatus.RUNNING.value


def test_start_emits_audit(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    client.post(_val_url(minimal_project_ids, did, vid, "start"), headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.VALIDATION_STARTED.value)
    ).first()
    assert row is not None


def test_start_again_returns_409(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    client.post(_val_url(minimal_project_ids, did, vid, "start"), headers=h)
    r2 = client.post(_val_url(minimal_project_ids, did, vid, "start"), headers=h)
    assert r2.status_code == 409


# ── Complete (PASSED) ─────────────────────────────────────────────────────────

def test_complete_passed_transitions_status(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    r = client.post(_val_url(minimal_project_ids, did, vid, "complete"),
                    json={"passed": True, "result_summary": "All tests green"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == ValidationStatus.PASSED.value


def test_complete_passed_creates_proof(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    r = client.post(_val_url(minimal_project_ids, did, vid, "complete"),
                    json={"passed": True, "result_summary": "Green"}, headers=h)
    proof_id = r.json().get("proof_object_id")
    assert proof_id is not None
    db_session.expire_all()
    proof = db_session.get(ProofObject, uuid.UUID(proof_id))
    assert proof is not None
    assert proof.proof_type == "VALIDATION_RUN_PASSED"


def test_complete_passed_emits_audit(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    client.post(_val_url(minimal_project_ids, did, vid, "complete"),
                json={"passed": True, "result_summary": "OK"}, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.VALIDATION_PASSED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert p["validation_id"] == vid
    # No result payload content in basic audit
    assert "result_payload_json" not in p


# ── Complete (FAILED) ─────────────────────────────────────────────────────────

def test_complete_failed_creates_proof(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    r = client.post(_val_url(minimal_project_ids, did, vid, "complete"),
                    json={"passed": False, "result_summary": "2 tests failed"}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == ValidationStatus.FAILED.value
    proof_id = r.json().get("proof_object_id")
    assert proof_id is not None
    db_session.expire_all()
    proof = db_session.get(ProofObject, uuid.UUID(proof_id))
    assert proof is not None
    assert proof.proof_type == "VALIDATION_RUN_FAILED"


def test_complete_requires_result_summary(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    r = client.post(_val_url(minimal_project_ids, did, vid, "complete"),
                    json={"passed": True, "result_summary": ""}, headers=h)
    assert r.status_code == 422


# ── Waive ─────────────────────────────────────────────────────────────────────

def test_waive_validation(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    r = client.post(_val_url(minimal_project_ids, did, vid, "waive"),
                    json={"reason": "Already validated in staging"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == ValidationStatus.WAIVED.value
    assert r.json()["result_summary"] == "Already validated in staging"


def test_waive_requires_reason(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    r = client.post(_val_url(minimal_project_ids, did, vid, "waive"),
                    json={"reason": ""}, headers=h)
    assert r.status_code == 422


def test_waive_emits_audit(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    client.post(_val_url(minimal_project_ids, did, vid, "waive"),
                json={"reason": "waived"}, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.VALIDATION_WAIVED.value)
    ).first()
    assert row is not None


# ── Terminal immutability ─────────────────────────────────────────────────────

def test_passed_run_is_immutable(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    client.post(_val_url(minimal_project_ids, did, vid, "complete"),
                json={"passed": True, "result_summary": "OK"}, headers=h)
    r = client.post(_val_url(minimal_project_ids, did, vid, "waive"),
                    json={"reason": "too late"}, headers=h)
    assert r.status_code == 409
    assert "immutable" in r.json()["detail"]


def test_failed_run_is_immutable(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    client.post(_val_url(minimal_project_ids, did, vid, "complete"),
                json={"passed": False, "result_summary": "Bad"}, headers=h)
    r = client.post(_val_url(minimal_project_ids, did, vid, "complete"),
                    json={"passed": True, "result_summary": "Override"}, headers=h)
    assert r.status_code == 409


def test_waived_run_is_immutable(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    client.post(_val_url(minimal_project_ids, did, vid, "waive"),
                json={"reason": "waived"}, headers=h)
    r = client.post(_val_url(minimal_project_ids, did, vid, "start"), headers=h)
    assert r.status_code == 409


# ── RBAC ─────────────────────────────────────────────────────────────────────

def test_viewer_cannot_complete(client, minimal_project_ids, db_session) -> None:
    viewer = _make_viewer(db_session, minimal_project_ids)
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    lr = client.post("/api/v1/auth/login", json=viewer)
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_val_url(minimal_project_ids, did, vid, "complete"),
                    json={"passed": True, "result_summary": "OK"}, headers=vh)
    assert r.status_code == 403


def test_viewer_cannot_waive(client, minimal_project_ids, db_session) -> None:
    viewer = _make_viewer(db_session, minimal_project_ids)
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    cv = client.post(_val_url(minimal_project_ids, did), json=_CREATE_BODY, headers=h)
    vid = cv.json()["id"]
    lr = client.post("/api/v1/auth/login", json=viewer)
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_val_url(minimal_project_ids, did, vid, "waive"),
                    json={"reason": "r"}, headers=vh)
    assert r.status_code == 403
