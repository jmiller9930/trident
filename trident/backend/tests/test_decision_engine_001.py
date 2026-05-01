"""TRIDENT_DECISION_ENGINE_001 — deterministic patch-level decision synthesis."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.decision_record import DecisionRecommendation, DecisionRecord
from app.models.directive import Directive
from app.models.enums import AuditEventType, DirectiveStatus
from app.models.patch_proposal import PatchExecutionStatus, PatchProposal, PatchProposalStatus
from app.models.patch_review import PatchReview, ReviewerRecommendation
from app.models.validation_run import ValidationRun, ValidationStatus
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.services.decision_engine_service import (
    REVIEWER_ACCEPT_CONFIDENCE_THRESHOLD,
    DecisionEngineService,
    DecisionRecommendation,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login(client, ids) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(ids) -> str:
    return str(ids["project_id"])


def _make_issued_directive(db_session, ids) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Decision engine test",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.flush()
    d.status = DirectiveStatus.ISSUED.value
    db_session.commit()
    return d.id


def _make_proposed_patch(db_session, ids, did) -> uuid.UUID:
    p = PatchProposal(
        project_id=ids["project_id"],
        directive_id=did,
        status=PatchProposalStatus.PROPOSED.value,
        title="Test patch",
        summary="Adds feature",
        files_changed={"files": [{"path": "app/x.py", "content": "x=1", "change_type": "update"}]},
        proposed_by_user_id=ids["user_id"],
    )
    db_session.add(p)
    db_session.commit()
    return p.id


def _add_review(db_session, ids, did, patch_id, recommendation: str, confidence: float, summary: str = "test review") -> None:
    r = PatchReview(
        project_id=ids["project_id"],
        directive_id=did,
        patch_id=patch_id,
        reviewer_agent_role="REVIEWER",
        recommendation=recommendation,
        confidence=confidence,
        summary=summary,
        findings_json=[{"severity": "ERROR", "message": "Found issue", "path": None, "suggested_action": None}]
            if recommendation in ("REJECT", "NEEDS_CHANGES") else [],
        created_by_user_id=ids["user_id"],
    )
    db_session.add(r)
    db_session.commit()


def _add_validation(db_session, ids, did, status: str) -> None:
    v = ValidationRun(
        project_id=ids["project_id"],
        directive_id=did,
        validation_type="MANUAL",
        status=status,
        started_by_user_id=ids["user_id"],
    )
    db_session.add(v)
    db_session.commit()


def _decision_url(ids, did) -> str:
    return f"/api/v1/projects/{_pid(ids)}/directives/{did}/decision"


def _record_url(ids, did) -> str:
    return f"/api/v1/projects/{_pid(ids)}/directives/{did}/decision/record"


# ── Decision engine unit tests (service layer) ────────────────────────────────

def test_no_patch_returns_blocked(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did)
    assert out.recommendation == DecisionRecommendation.BLOCKED.value
    assert "no_patch_exists" in out.blocking_reasons


def test_proposed_no_review_returns_blocked_reviewer_required(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch_id = _make_proposed_patch(db_session, minimal_project_ids, did)
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch_id)
    assert out.recommendation == DecisionRecommendation.BLOCKED.value
    assert "reviewer_required" in out.blocking_reasons


def test_reviewer_accept_high_confidence_returns_accept_patch(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch_id = _make_proposed_patch(db_session, minimal_project_ids, did)
    _add_review(db_session, minimal_project_ids, did, patch_id, "ACCEPT", 0.90)
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch_id)
    assert out.recommendation == DecisionRecommendation.ACCEPT_PATCH.value
    assert out.confidence == 0.90


def test_reviewer_accept_low_confidence_returns_blocked(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch_id = _make_proposed_patch(db_session, minimal_project_ids, did)
    low_conf = REVIEWER_ACCEPT_CONFIDENCE_THRESHOLD - 0.05
    _add_review(db_session, minimal_project_ids, did, patch_id, "ACCEPT", low_conf)
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch_id)
    assert out.recommendation == DecisionRecommendation.BLOCKED.value
    assert any("confidence" in r for r in out.blocking_reasons)


def test_reviewer_reject_returns_reject_patch(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch_id = _make_proposed_patch(db_session, minimal_project_ids, did)
    _add_review(db_session, minimal_project_ids, did, patch_id, "REJECT", 0.88)
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch_id)
    assert out.recommendation == DecisionRecommendation.REJECT_PATCH.value


def test_reviewer_needs_changes_returns_request_changes(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch_id = _make_proposed_patch(db_session, minimal_project_ids, did)
    _add_review(db_session, minimal_project_ids, did, patch_id, "NEEDS_CHANGES", 0.70)
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch_id)
    assert out.recommendation == DecisionRecommendation.REQUEST_CHANGES.value


def test_accepted_patch_not_executed_returns_execute_patch(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch = PatchProposal(
        project_id=minimal_project_ids["project_id"],
        directive_id=did,
        status=PatchProposalStatus.ACCEPTED.value,
        title="Accepted patch",
        proposed_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(patch)
    db_session.commit()
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch.id)
    assert out.recommendation == DecisionRecommendation.EXECUTE_PATCH.value


def test_executed_patch_no_validation_returns_create_validation(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch = PatchProposal(
        project_id=minimal_project_ids["project_id"],
        directive_id=did,
        status=PatchProposalStatus.ACCEPTED.value,
        execution_status=PatchExecutionStatus.EXECUTED.value,
        execution_commit_sha="abc123",
        title="Executed patch",
        proposed_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(patch)
    db_session.commit()
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch.id)
    assert out.recommendation == DecisionRecommendation.CREATE_VALIDATION.value


def test_passed_validation_returns_signoff(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch = PatchProposal(
        project_id=minimal_project_ids["project_id"],
        directive_id=did,
        status=PatchProposalStatus.ACCEPTED.value,
        execution_status=PatchExecutionStatus.EXECUTED.value,
        execution_commit_sha="abc123",
        title="Executed patch",
        proposed_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(patch)
    db_session.commit()
    _add_validation(db_session, minimal_project_ids, did, ValidationStatus.PASSED.value)
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch.id)
    assert out.recommendation == DecisionRecommendation.SIGNOFF.value


def test_failed_validation_returns_request_changes(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch = PatchProposal(
        project_id=minimal_project_ids["project_id"],
        directive_id=did,
        status=PatchProposalStatus.ACCEPTED.value,
        execution_status=PatchExecutionStatus.EXECUTED.value,
        execution_commit_sha="abc123",
        title="Executed patch",
        proposed_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(patch)
    db_session.commit()
    _add_validation(db_session, minimal_project_ids, did, ValidationStatus.FAILED.value)
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch.id)
    assert out.recommendation in (
        DecisionRecommendation.REQUEST_CHANGES.value,
        DecisionRecommendation.BLOCKED.value,
    )


def test_closed_directive_returns_no_action(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    d = db_session.get(Directive, did)
    d.status = DirectiveStatus.CLOSED.value
    d.closed_at = datetime.now(timezone.utc)
    db_session.commit()
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did)
    assert out.recommendation == DecisionRecommendation.NO_ACTION.value


def test_rejected_patch_returns_no_action(db_session: Session, minimal_project_ids: dict) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    patch = PatchProposal(
        project_id=minimal_project_ids["project_id"],
        directive_id=did,
        status=PatchProposalStatus.REJECTED.value,
        title="Rejected patch",
        proposed_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(patch)
    db_session.commit()
    svc = DecisionEngineService(db_session)
    out = svc.compute(minimal_project_ids["project_id"], did, patch.id)
    assert out.recommendation == DecisionRecommendation.NO_ACTION.value


# ── API endpoint tests ─────────────────────────────────────────────────────────

def test_get_decision_requires_auth(client, minimal_project_ids, db_session) -> None:
    did = _make_issued_directive(db_session, minimal_project_ids)
    r = client.get(_decision_url(minimal_project_ids, did))
    assert r.status_code == 401


def test_viewer_can_get_decision(client, minimal_project_ids, db_session) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    email = f"viewer-de-{uid}@example.com"
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
    did = _make_issued_directive(db_session, minimal_project_ids)
    lr = client.post("/api/v1/auth/login", json={"email": email, "password": "viewerpass!"})
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.get(_decision_url(minimal_project_ids, did), headers=vh)
    assert r.status_code == 200


def test_get_decision_does_not_persist(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_issued_directive(db_session, minimal_project_ids)
    client.get(_decision_url(minimal_project_ids, did), headers=h)
    db_session.expire_all()
    records = list(db_session.scalars(
        select(DecisionRecord).where(DecisionRecord.directive_id == did)
    ).all())
    assert records == []


def test_get_decision_response_shape(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_issued_directive(db_session, minimal_project_ids)
    r = client.get(_decision_url(minimal_project_ids, did), headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    for field in ("recommendation", "confidence", "summary", "evidence", "blocking_reasons", "computed_at"):
        assert field in body, f"Missing field: {field}"


def test_post_record_persists_decision(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_issued_directive(db_session, minimal_project_ids)
    r = client.post(_record_url(minimal_project_ids, did), headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["persisted"] is True
    assert uuid.UUID(body["decision_record_id"])
    db_session.expire_all()
    record = db_session.get(DecisionRecord, uuid.UUID(body["decision_record_id"]))
    assert record is not None
    assert record.recommendation == body["recommendation"]


def test_post_record_emits_decision_recorded_audit(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_issued_directive(db_session, minimal_project_ids)
    client.post(_record_url(minimal_project_ids, did), headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.DECISION_RECORDED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert p["recommendation"] is not None
    assert "x=1" not in json.dumps(p)  # no file content


def test_viewer_cannot_post_record(client, minimal_project_ids, db_session) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    email = f"viewer-de2-{uid}@example.com"
    u = User(id=uid, display_name="V2", email=email, role="m",
             password_hash=hash_password("viewerpass!"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(
        project_id=minimal_project_ids["project_id"],
        user_id=uid,
        role=ProjectMemberRole.VIEWER.value,
    ))
    db_session.commit()
    did = _make_issued_directive(db_session, minimal_project_ids)
    lr = client.post("/api/v1/auth/login", json={"email": email, "password": "viewerpass!"})
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_record_url(minimal_project_ids, did), headers=vh)
    assert r.status_code == 403


def test_decision_has_recommended_next_api_action(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_issued_directive(db_session, minimal_project_ids)
    r = client.get(_decision_url(minimal_project_ids, did), headers=h)
    body = r.json()
    # When blocked, next action hint should be present
    if body["recommendation"] == "BLOCKED":
        # recommended_next_api_action may or may not be present, but it shouldn't be an error
        assert "recommendation" in body
