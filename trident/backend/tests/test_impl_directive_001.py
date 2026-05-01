"""TRIDENT_IMPLEMENTATION_DIRECTIVE_001 — control plane acceptance (API-level)."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType, DirectiveStatus
from app.models.state_transition_log import StateTransitionLog


def test_register_login_refresh_project_invite_directive_issue_audit(client, db_session) -> None:
    r0 = client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner-impl001@example.com",
            "password": "longpassword1",
            "display_name": "Owner",
        },
    )
    assert r0.status_code == 201, r0.text
    owner_token = r0.json()["tokens"]["access_token"]
    owner_refresh = r0.json()["tokens"]["refresh_token"]
    owner_id = r0.json()["user"]["id"]
    oh = {"Authorization": f"Bearer {owner_token}"}

    rf = client.post("/api/v1/auth/refresh", json={"refresh_token": owner_refresh})
    assert rf.status_code == 200, rf.text
    assert rf.json()["access_token"]

    li = client.post(
        "/api/v1/auth/login",
        json={"email": "owner-impl001@example.com", "password": "longpassword1"},
    )
    assert li.status_code == 200, li.text

    cp = client.post(
        "/api/v1/projects/",
        json={"name": "P1", "allowed_root_path": "/tmp/p1"},
        headers=oh,
    )
    assert cp.status_code == 201, cp.text
    pid = cp.json()["id"]

    r_invitee = client.post(
        "/api/v1/auth/register",
        json={
            "email": "viewer-impl001@example.com",
            "password": "longpassword2",
            "display_name": "Invitee",
        },
    )
    assert r_invitee.status_code == 201, r_invitee.text

    inv = client.post(
        "/api/v1/members/invites",
        json={"project_id": pid, "email": "viewer-impl001@example.com", "role": "VIEWER"},
        headers=oh,
    )
    assert inv.status_code == 201, inv.text
    tok = inv.json()["token"]

    vi = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer-impl001@example.com", "password": "longpassword2"},
    )
    assert vi.status_code == 200, vi.text
    vh = {"Authorization": f"Bearer {vi.json()['tokens']['access_token']}"}

    acc = client.post("/api/v1/members/accept", json={"token": tok}, headers=vh)
    assert acc.status_code == 200, acc.text
    assert acc.json()["status"] == "joined"

    mem = client.get(f"/api/v1/members/projects/{pid}", headers=vh)
    assert mem.status_code == 200, mem.text
    member_user_ids = {m["user_id"] for m in mem.json()["items"]}
    assert len(member_user_ids) >= 2

    dc = client.post(
        "/api/v1/directives/",
        json={"project_id": pid, "title": "Directive one"},
        headers=oh,
    )
    assert dc.status_code == 200, dc.text
    body = dc.json()
    did = body["directive"]["id"]
    assert body["directive"]["created_by_user_id"] == owner_id
    assert body["directive"]["project_id"] == pid

    bad_issue = client.post(f"/api/v1/directives/{did}/issue", headers=vh)
    assert bad_issue.status_code == 403

    ok_issue = client.post(f"/api/v1/directives/{did}/issue", headers=oh)
    assert ok_issue.status_code == 200, ok_issue.text
    assert ok_issue.json()["status"] == DirectiveStatus.ISSUED.value

    dup_issue = client.post(f"/api/v1/directives/{did}/issue", headers=oh)
    assert dup_issue.status_code == 409

    db_session.expire_all()
    did_uuid = uuid.UUID(did)
    st_row = db_session.scalars(
        select(StateTransitionLog).where(StateTransitionLog.directive_id == did_uuid)
    ).first()
    assert st_row is not None
    assert st_row.from_state == DirectiveStatus.DRAFT.value
    assert st_row.to_state == DirectiveStatus.ISSUED.value

    audit_cp = db_session.scalars(
        select(AuditEvent).where(
            AuditEvent.event_type == AuditEventType.CONTROL_PLANE_ACTION.value,
            AuditEvent.actor_id == owner_id,
        )
    ).all()
    assert len(audit_cp) >= 1
