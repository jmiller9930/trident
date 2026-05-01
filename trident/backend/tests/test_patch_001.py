"""TRIDENT_IMPLEMENTATION_DIRECTIVE_PATCH_001 — governed patch proposal review."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.patch_proposal import PatchProposal, PatchProposalStatus
from app.models.proof_object import ProofObject
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


# ── Helpers ──────────────────────────────────────────────────────────────────

def _login(client, ids) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(ids) -> str:
    return str(ids["project_id"])


def _create_directive(db_session, ids) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Test directive for patch",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


def _patch_url(ids, did, patch_id=None) -> str:
    pid = _pid(ids)
    base = f"/api/v1/projects/{pid}/directives/{did}/patches"
    return base if patch_id is None else f"{base}/{patch_id}"


def _make_viewer(db_session, ids) -> dict:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    email = f"viewer-patch-{uid}@example.com"
    u = User(id=uid, display_name="V", email=email, role="member",
             password_hash=hash_password("viewerpass!"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(
        project_id=ids["project_id"], user_id=uid, role=ProjectMemberRole.VIEWER.value
    ))
    db_session.commit()
    return {"email": email, "password": "viewerpass!"}


_DIFF = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new\n"
_BODY = {
    "title": "Add new feature",
    "summary": "Changes foo.py",
    "files_changed": {"foo.py": "modified"},
    "unified_diff": _DIFF,
}


# ── RBAC ─────────────────────────────────────────────────────────────────────

def test_create_patch_requires_auth(client, minimal_project_ids, db_session) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    r = client.post(_patch_url(minimal_project_ids, did), json=_BODY)
    assert r.status_code == 401


def test_viewer_cannot_create_patch(client, minimal_project_ids, db_session) -> None:
    viewer = _make_viewer(db_session, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    lr = client.post("/api/v1/auth/login", json=viewer)
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=vh)
    assert r.status_code == 403


def test_viewer_cannot_accept_patch(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    viewer = _make_viewer(db_session, minimal_project_ids)
    lr = client.post("/api/v1/auth/login", json=viewer)
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_patch_url(minimal_project_ids, did, patch_id) + "/accept", headers=vh)
    assert r.status_code == 403


def test_viewer_cannot_reject_patch(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    viewer = _make_viewer(db_session, minimal_project_ids)
    lr = client.post("/api/v1/auth/login", json=viewer)
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_patch_url(minimal_project_ids, did, patch_id) + "/reject",
                    json={"reason": "no"}, headers=vh)
    assert r.status_code == 403


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_patch_returns_proposed(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    r = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == PatchProposalStatus.PROPOSED.value
    assert body["title"] == "Add new feature"
    assert "unified_diff" in body


def test_create_patch_persists_to_db(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    r = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = uuid.UUID(r.json()["id"])
    db_session.expire_all()
    row = db_session.get(PatchProposal, patch_id)
    assert row is not None
    assert row.status == PatchProposalStatus.PROPOSED.value
    assert row.unified_diff == _DIFF


def test_create_patch_emits_patch_proposed_audit(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.PATCH_PROPOSED.value)
    ).first()
    assert row is not None
    assert row.event_payload_json["title"] == "Add new feature"


def test_create_patch_directive_mismatch_rejected(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    wrong_did = str(uuid.uuid4())
    r = client.post(_patch_url(minimal_project_ids, wrong_did), json=_BODY, headers=h)
    assert r.status_code == 422
    assert "directive_not_in_project" in r.json()["detail"]


# ── List / get ────────────────────────────────────────────────────────────────

def test_list_patches(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    client.post(_patch_url(minimal_project_ids, did), json={**_BODY, "title": "Second"}, headers=h)
    r = client.get(_patch_url(minimal_project_ids, did), headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2


def test_get_patch_returns_detail(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    r = client.get(_patch_url(minimal_project_ids, did, patch_id), headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["unified_diff"] == _DIFF


def test_get_patch_404_for_unknown(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    r = client.get(_patch_url(minimal_project_ids, did, str(uuid.uuid4())), headers=h)
    assert r.status_code == 404


# ── Accept ────────────────────────────────────────────────────────────────────

def test_accept_patch_transitions_status(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    r = client.post(_patch_url(minimal_project_ids, did, patch_id) + "/accept", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == PatchProposalStatus.ACCEPTED.value
    assert body["accepted_by_user_id"] == str(minimal_project_ids["user_id"])
    assert body["accepted_at"] is not None


def test_accept_patch_creates_proof_object(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    r = client.post(_patch_url(minimal_project_ids, did, patch_id) + "/accept", headers=h)
    proof_id_str = r.json()["proof_object_id"]
    assert proof_id_str is not None
    db_session.expire_all()
    proof = db_session.get(ProofObject, uuid.UUID(proof_id_str))
    assert proof is not None
    assert proof.proof_type == "GIT_DIFF"


def test_accept_patch_emits_audit(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id) + "/accept", headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.PATCH_ACCEPTED.value)
    ).first()
    assert row is not None
    assert row.event_payload_json["patch_id"] == patch_id


def test_accept_already_accepted_returns_409(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id) + "/accept", headers=h)
    # Create another patch and try to accept it — directive already has accepted patch
    cp2 = client.post(_patch_url(minimal_project_ids, did), json={**_BODY, "title": "Alt"}, headers=h)
    patch_id2 = cp2.json()["id"]
    r2 = client.post(_patch_url(minimal_project_ids, did, patch_id2) + "/accept", headers=h)
    assert r2.status_code == 409
    assert "directive_already_has_accepted_patch" in r2.json()["detail"]


def test_accepted_patch_is_immutable(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id) + "/accept", headers=h)
    # Try to reject the accepted patch
    r = client.post(_patch_url(minimal_project_ids, did, patch_id) + "/reject",
                    json={"reason": "too late"}, headers=h)
    assert r.status_code == 409
    assert "immutable" in r.json()["detail"]


# ── Reject ────────────────────────────────────────────────────────────────────

def test_reject_patch_transitions_status(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    r = client.post(_patch_url(minimal_project_ids, did, patch_id) + "/reject",
                    json={"reason": "Not ready"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == PatchProposalStatus.REJECTED.value
    assert body["rejection_reason"] == "Not ready"


def test_reject_without_reason_fails_validation(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    r = client.post(_patch_url(minimal_project_ids, did, patch_id) + "/reject",
                    json={"reason": ""}, headers=h)
    assert r.status_code == 422


def test_reject_emits_audit(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id) + "/reject",
                json={"reason": "Bad impl"}, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.PATCH_REJECTED.value)
    ).first()
    assert row is not None
    assert row.event_payload_json["rejection_reason"] == "Bad impl"


def test_rejected_patch_is_immutable(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_directive(db_session, minimal_project_ids)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_BODY, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id) + "/reject",
                json={"reason": "Bad"}, headers=h)
    r = client.post(_patch_url(minimal_project_ids, did, patch_id) + "/accept", headers=h)
    assert r.status_code == 409
    assert "immutable" in r.json()["detail"]
