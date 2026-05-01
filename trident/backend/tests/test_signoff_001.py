"""TRIDENT_IMPLEMENTATION_DIRECTIVE_SIGNOFF_001 — directive sign-off and closure."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.audit_event import AuditEvent
from app.models.directive import Directive
from app.models.enums import AuditEventType, DirectiveStatus
from app.models.proof_object import ProofObject
from app.models.validation_run import ValidationRun, ValidationStatus
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _login(client, ids) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(ids):
    return str(ids["project_id"])


def _make_issued_directive(client, db_session, ids) -> tuple[uuid.UUID, dict]:
    h = _login(client, ids)
    pid = _pid(ids)
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Signoff test directive",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    r = client.post(f"/api/v1/directives/{d.id}/issue", headers=h)
    assert r.status_code == 200, r.text
    return d.id, h


def _val_url(ids, did) -> str:
    return f"/api/v1/projects/{_pid(ids)}/directives/{did}/validations"


def _add_validation(client, ids, did, h, passed: bool) -> str:
    cv = client.post(_val_url(ids, did), json={"validation_type": "MANUAL"}, headers=h)
    assert cv.status_code == 201, cv.text
    vid = cv.json()["id"]
    cr = client.post(
        f"{_val_url(ids, did)}/{vid}/complete",
        json={"passed": passed, "result_summary": "done"},
        headers=h,
    )
    assert cr.status_code == 200, cr.text
    return vid


def _add_waived_validation(client, ids, did, h) -> str:
    cv = client.post(_val_url(ids, did), json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"{_val_url(ids, did)}/{vid}/waive",
                json={"reason": "waived"}, headers=h)
    return vid


def _signoff_url(did) -> str:
    return f"/api/v1/directives/{did}/signoff"


# ── Eligibility ───────────────────────────────────────────────────────────────

def test_cannot_signoff_with_no_validations(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    r = client.post(_signoff_url(did), headers=h)
    assert r.status_code == 422
    assert "no_validation_runs" in r.json()["detail"]


def test_cannot_signoff_with_only_failed_validations(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    _add_validation(client, minimal_project_ids, did, h, passed=False)
    r = client.post(_signoff_url(did), headers=h)
    assert r.status_code == 422
    assert "no_passed_validations" in r.json()["detail"]


def test_cannot_signoff_with_unwaived_failure(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    _add_validation(client, minimal_project_ids, did, h, passed=True)
    _add_validation(client, minimal_project_ids, did, h, passed=False)  # FAILED, not waived
    r = client.post(_signoff_url(did), headers=h)
    assert r.status_code == 422
    assert "unwaived_failure" in r.json()["detail"]


def test_can_signoff_with_only_passed_validations(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    _add_validation(client, minimal_project_ids, did, h, passed=True)
    r = client.post(_signoff_url(did), headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == DirectiveStatus.CLOSED.value


def test_can_signoff_with_passed_and_waived(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    _add_validation(client, minimal_project_ids, did, h, passed=True)
    _add_waived_validation(client, minimal_project_ids, did, h)
    r = client.post(_signoff_url(did), headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == DirectiveStatus.CLOSED.value


# ── Closure state ──────────────────────────────────────────────────────────────

def test_signoff_sets_status_closed(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    _add_validation(client, minimal_project_ids, did, h, passed=True)
    client.post(_signoff_url(did), headers=h)
    db_session.expire_all()
    d = db_session.get(Directive, did)
    assert d is not None
    assert d.status == DirectiveStatus.CLOSED.value
    assert d.closed_at is not None
    assert d.closed_by_user_id == minimal_project_ids["user_id"]


def test_signoff_sets_closed_at_and_closed_by(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    _add_validation(client, minimal_project_ids, did, h, passed=True)
    r = client.post(_signoff_url(did), headers=h)
    body = r.json()
    assert body["closed_at"] is not None
    assert body["closed_by_user_id"] == str(minimal_project_ids["user_id"])


def test_second_signoff_returns_409(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    _add_validation(client, minimal_project_ids, did, h, passed=True)
    client.post(_signoff_url(did), headers=h)
    r2 = client.post(_signoff_url(did), headers=h)
    assert r2.status_code == 409
    assert "directive_already_closed" in r2.json()["detail"]


# ── Audit + proof ─────────────────────────────────────────────────────────────

def test_signoff_emits_signoff_completed_audit(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    _add_validation(client, minimal_project_ids, did, h, passed=True)
    client.post(_signoff_url(did), headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.SIGNOFF_COMPLETED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert p["directive_id"] == str(did)
    assert p["validation_summary"]["passed_count"] == 1
    assert "result_payload_json" not in p


def test_signoff_creates_proof_object(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    _add_validation(client, minimal_project_ids, did, h, passed=True)
    r = client.post(_signoff_url(did), headers=h)
    body = r.json()
    assert body.get("proof_object_id") is not None
    db_session.expire_all()
    proof = db_session.get(ProofObject, uuid.UUID(body["proof_object_id"]))
    assert proof is not None
    assert proof.proof_type == "DIRECTIVE_SIGNOFF"


# ── Post-closure enforcement ──────────────────────────────────────────────────

def _close_directive(client, ids, db_session) -> tuple[uuid.UUID, dict]:
    did, h = _make_issued_directive(client, db_session, ids)
    _add_validation(client, ids, did, h, passed=True)
    client.post(_signoff_url(did), headers=h)
    return did, h


def test_patch_creation_blocked_after_closure(client, minimal_project_ids, db_session) -> None:
    did, h = _close_directive(client, minimal_project_ids, db_session)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/directives/{did}/patches",
        json={"title": "Late patch"},
        headers=h,
    )
    assert r.status_code == 409
    assert "directive_closed" in r.json()["detail"]


def test_validation_creation_blocked_after_closure(client, minimal_project_ids, db_session) -> None:
    did, h = _close_directive(client, minimal_project_ids, db_session)
    r = client.post(_val_url(minimal_project_ids, did),
                    json={"validation_type": "MANUAL"}, headers=h)
    assert r.status_code == 409
    assert "directive_closed" in r.json()["detail"]


def test_validation_complete_blocked_after_closure(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    # Create validation before closing
    cv = client.post(_val_url(minimal_project_ids, did),
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    _add_validation(client, minimal_project_ids, did, h, passed=True)
    client.post(_signoff_url(did), headers=h)  # close
    # Now try to complete the PENDING validation
    r = client.post(
        f"{_val_url(minimal_project_ids, did)}/{vid}/complete",
        json={"passed": True, "result_summary": "too late"},
        headers=h,
    )
    assert r.status_code == 409
    assert "directive_closed" in r.json()["detail"]


# ── RBAC ─────────────────────────────────────────────────────────────────────

def test_signoff_requires_admin(client, minimal_project_ids, db_session) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    did, _ = _make_issued_directive(client, db_session, minimal_project_ids)
    uid = uuid.uuid4()
    email = f"cont-signoff-{uid}@example.com"
    u = User(id=uid, display_name="C", email=email, role="m",
             password_hash=hash_password("pass1234!"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(
        project_id=minimal_project_ids["project_id"],
        user_id=uid,
        role=ProjectMemberRole.CONTRIBUTOR.value,
    ))
    db_session.commit()
    lr = client.post("/api/v1/auth/login", json={"email": email, "password": "pass1234!"})
    ch = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_signoff_url(did), headers=ch)
    assert r.status_code == 403
