"""TRIDENT_SYSTEM_GUARDRAILS_001 — cross-system invariant checks."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.directive import Directive
from app.models.enums import AuditEventType, DirectiveStatus
from app.models.git_branch_log import GitBranchLog
from app.models.patch_proposal import PatchExecutionStatus, PatchProposal, PatchProposalStatus
from app.models.validation_run import ValidationRun, ValidationStatus
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.services.system_guardrail_service import SystemGuardrailService


# ── Helpers ──────────────────────────────────────────────────────────────────

def _login(client, ids) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(ids) -> str:
    return str(ids["project_id"])


def _make_issued_directive(client, db_session, ids) -> tuple[uuid.UUID, dict]:
    h = _login(client, ids)
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Guardrail test directive",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    client.post(f"/api/v1/directives/{d.id}/issue", headers=h)
    db_session.expire_all()
    return d.id, h


def _close_directive(client, db_session, ids) -> tuple[uuid.UUID, dict]:
    did, h = _make_issued_directive(client, db_session, ids)
    pid = _pid(ids)
    cv = client.post(f"/api/v1/projects/{pid}/directives/{did}/validations",
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
                json={"passed": True, "result_summary": "OK"}, headers=h)
    client.post(f"/api/v1/directives/{did}/signoff", headers=h)
    db_session.expire_all()
    return did, h


def _gr_url(ids, did) -> str:
    return f"/api/v1/projects/{_pid(ids)}/directives/{did}/guardrails"


# ── Happy path ────────────────────────────────────────────────────────────────

def test_healthy_directive_returns_pass(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    r = client.get(_gr_url(minimal_project_ids, did), headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PASS"
    assert body["violations"] == []


def test_closed_directive_with_all_artifacts_returns_pass(client, minimal_project_ids, db_session) -> None:
    did, h = _close_directive(client, db_session, minimal_project_ids)
    r = client.get(_gr_url(minimal_project_ids, did), headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PASS", body["violations"]


# ── Closed without signoff audit ─────────────────────────────────────────────

def test_closed_without_signoff_audit_returns_fail(db_session: Session, minimal_project_ids: dict) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Broken closure",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.flush()
    # Force CLOSED without going through signoff flow
    d.status = DirectiveStatus.CLOSED.value
    d.closed_at = datetime.now(timezone.utc)
    d.closed_by_user_id = minimal_project_ids["user_id"]
    db_session.commit()

    svc = SystemGuardrailService(db_session)
    result = svc.check_directive(d.id, minimal_project_ids["project_id"])
    assert result.status == "FAIL"
    codes = {v.code for v in result.violations}
    assert "CLOSED_MISSING_SIGNOFF_AUDIT" in codes
    assert "CLOSED_WITHOUT_PASSED_VALIDATION" in codes


# ── Executed patch missing commit log ─────────────────────────────────────────

def test_executed_patch_missing_branch_log_returns_fail(db_session: Session, minimal_project_ids: dict) -> None:
    body_req = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Patch integrity test",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body_req)
    db_session.flush()

    # Create an EXECUTED patch without a matching git_branch_log
    patch = PatchProposal(
        project_id=minimal_project_ids["project_id"],
        directive_id=d.id,
        status=PatchProposalStatus.ACCEPTED.value,
        title="Executed patch",
        execution_status=PatchExecutionStatus.EXECUTED.value,
        execution_commit_sha="abc123def456abc123def456abc123def456abc1",
        execution_branch_name="trident/aaaabbbb/patch-integrity-test",
        proposed_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(patch)
    db_session.commit()

    svc = SystemGuardrailService(db_session)
    result = svc.check_directive(d.id, minimal_project_ids["project_id"])
    assert result.status == "FAIL"
    codes = {v.code for v in result.violations}
    assert "EXECUTED_PATCH_MISSING_BRANCH_LOG" in codes


# ── Commit without branch_created ─────────────────────────────────────────────

def test_commit_without_branch_created_returns_fail(db_session: Session, minimal_project_ids: dict) -> None:
    body_req = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Git linkage test",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body_req)
    db_session.flush()

    # commit_pushed without branch_created
    db_session.add(GitBranchLog(
        project_id=minimal_project_ids["project_id"],
        directive_id=d.id,
        provider="github",
        branch_name="trident/aaaabbbb/git-linkage-test",
        commit_sha="deadbeef0000000000000000000000000000dead",
        commit_message="orphan commit",
        created_by_user_id=minimal_project_ids["user_id"],
        event_type="commit_pushed",
    ))
    db_session.commit()

    svc = SystemGuardrailService(db_session)
    result = svc.check_directive(d.id, minimal_project_ids["project_id"])
    assert result.status == "FAIL"
    codes = {v.code for v in result.violations}
    assert "COMMIT_WITHOUT_BRANCH_CREATED" in codes


# ── Accepted patch missing PATCH_ACCEPTED audit ───────────────────────────────

def test_accepted_patch_missing_audit_returns_fail(db_session: Session, minimal_project_ids: dict) -> None:
    body_req = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Audit completeness test",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body_req)
    db_session.flush()

    # ACCEPTED patch with no PATCH_ACCEPTED audit
    patch = PatchProposal(
        project_id=minimal_project_ids["project_id"],
        directive_id=d.id,
        status=PatchProposalStatus.ACCEPTED.value,
        title="No audit patch",
        proposed_by_user_id=minimal_project_ids["user_id"],
        accepted_by_user_id=minimal_project_ids["user_id"],
        accepted_at=datetime.now(timezone.utc),
    )
    db_session.add(patch)
    db_session.commit()

    svc = SystemGuardrailService(db_session)
    result = svc.check_directive(d.id, minimal_project_ids["project_id"])
    assert result.status == "FAIL"
    codes = {v.code for v in result.violations}
    assert "ACCEPTED_PATCH_MISSING_AUDIT" in codes


# ── Endpoint RBAC ─────────────────────────────────────────────────────────────

def test_guardrails_endpoint_requires_admin(client, minimal_project_ids, db_session) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    email = f"viewer-gr-{uid}@example.com"
    u = User(id=uid, display_name="V", email=email, role="m",
             password_hash=hash_password("viewerpass!"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(
        project_id=minimal_project_ids["project_id"],
        user_id=uid,
        role=ProjectMemberRole.VIEWER.value,
    ))
    db_session.commit()
    did, _ = _make_issued_directive(client, db_session, minimal_project_ids)
    lr = client.post("/api/v1/auth/login", json={"email": email, "password": "viewerpass!"})
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.get(_gr_url(minimal_project_ids, did), headers=vh)
    assert r.status_code == 403


def test_guardrails_endpoint_requires_auth(client, minimal_project_ids, db_session) -> None:
    did, _ = _make_issued_directive(client, db_session, minimal_project_ids)
    r = client.get(_gr_url(minimal_project_ids, did))
    assert r.status_code == 401


# ── Violation payload shape ───────────────────────────────────────────────────

def test_violation_payload_shape(db_session: Session, minimal_project_ids: dict) -> None:
    body_req = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Payload shape test",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body_req)
    db_session.flush()
    d.status = DirectiveStatus.CLOSED.value
    d.closed_at = datetime.now(timezone.utc)
    d.closed_by_user_id = minimal_project_ids["user_id"]
    db_session.commit()

    svc = SystemGuardrailService(db_session)
    result = svc.check_directive(d.id, minimal_project_ids["project_id"])
    assert result.status == "FAIL"
    for v in result.violations:
        d_v = v.as_dict()
        for field in ("code", "severity", "message", "related_table"):
            assert field in d_v, f"Missing field: {field}"
        assert d_v["severity"] in ("INFO", "WARNING", "ERROR", "BLOCKING")


# ── Enforcement hooks ─────────────────────────────────────────────────────────

def test_enforcement_blocks_execute_on_non_accepted_patch(db_session: Session, minimal_project_ids: dict) -> None:
    """Service-layer test: guardrail blocks execution of PROPOSED patch."""
    from app.models.patch_proposal import PatchProposal, PatchProposalStatus
    from app.services.system_guardrail_service import SystemGuardrailService, GuardrailViolationError

    body_req = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Enforcement block test",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body_req)
    db_session.flush()

    patch = PatchProposal(
        project_id=minimal_project_ids["project_id"],
        directive_id=d.id,
        status=PatchProposalStatus.PROPOSED.value,
        title="Not accepted",
        proposed_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(patch)
    db_session.commit()

    svc = SystemGuardrailService(db_session)
    with pytest.raises(GuardrailViolationError) as ei:
        svc.assert_patch_executable(
            patch=patch,
            directive_id=d.id,
            project_id=minimal_project_ids["project_id"],
            user_id=minimal_project_ids["user_id"],
        )
    assert ei.value.violation.code == "PATCH_NOT_ACCEPTED"
    assert ei.value.violation.severity == "BLOCKING"


def test_guardrail_result_has_status_field(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    r = client.get(_gr_url(minimal_project_ids, did), headers=h)
    body = r.json()
    assert "status" in body
    assert "violations" in body
    assert "checked_at" in body
    assert "violation_count" in body
    assert isinstance(body["violations"], list)


def test_guardrail_audit_on_guardrail_block(db_session: Session, minimal_project_ids: dict) -> None:
    """Guardrail BLOCKING violation emits CONTROL_PLANE_ACTION audit."""
    body_req = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Audit on block test",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body_req)
    db_session.flush()
    db_session.commit()

    patch = PatchProposal(
        project_id=minimal_project_ids["project_id"],
        directive_id=d.id,
        status=PatchProposalStatus.PROPOSED.value,  # not accepted
        title="Will fail guardrail",
        proposed_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(patch)
    db_session.commit()

    svc = SystemGuardrailService(db_session)
    from app.services.system_guardrail_service import GuardrailViolationError
    try:
        svc.assert_patch_executable(
            patch=patch,
            directive_id=d.id,
            project_id=minimal_project_ids["project_id"],
            user_id=minimal_project_ids["user_id"],
        )
    except GuardrailViolationError:
        pass

    db_session.commit()
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(
            AuditEvent.event_type == AuditEventType.CONTROL_PLANE_ACTION.value,
            AuditEvent.directive_id == d.id,
        )
    ).first()
    assert row is not None
    assert row.event_payload_json.get("blocked") is True
    assert row.event_payload_json.get("violation_code") == "PATCH_NOT_ACCEPTED"
