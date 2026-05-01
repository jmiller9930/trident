"""TRIDENT_AGENT_REVIEWER_001 — governed Reviewer agent runtime."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.model_router.model_router_service import ModelRouterResult, ModelRouterService
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.patch_proposal import PatchProposal, PatchProposalStatus
from app.models.patch_review import PatchReview, ReviewerRecommendation
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.services.reviewer_runtime_service import (
    ReviewerOutputParseError,
    ReviewerRuntimeBlockedError,
    ReviewerRuntimeService,
    _parse_reviewer_output,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

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
        title="Reviewer test directive",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    client.post(f"/api/v1/directives/{d.id}/issue", headers=h)
    db_session.expire_all()
    return d.id, h


def _create_proposed_patch(client, ids, did, h) -> str:
    pid = _pid(ids)
    r = client.post(
        f"/api/v1/projects/{pid}/directives/{did}/patches",
        json={
            "title": "Add logging",
            "summary": "Adds structured logging",
            "files_changed": {"files": [{"path": "app/main.py", "content": "import logging\n", "change_type": "update"}]},
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _reviewer_url(ids, did, patch_id) -> str:
    pid = _pid(ids)
    return f"/api/v1/projects/{pid}/directives/{did}/patches/{patch_id}/agents/reviewer/run"


ACCEPT_JSON = json.dumps({
    "recommendation": "ACCEPT",
    "confidence": 0.92,
    "summary": "Patch looks good, minimal risk.",
    "findings": [],
})

REJECT_JSON = json.dumps({
    "recommendation": "REJECT",
    "confidence": 0.88,
    "summary": "Patch has a critical bug.",
    "findings": [
        {"severity": "BLOCKING", "message": "Division by zero in line 5", "path": "app/main.py",
         "suggested_action": "Add null check before division."},
    ],
})

NEEDS_CHANGES_JSON = json.dumps({
    "recommendation": "NEEDS_CHANGES",
    "confidence": 0.70,
    "summary": "Minor improvements needed.",
    "findings": [
        {"severity": "WARNING", "message": "Missing docstring", "path": "app/main.py"},
    ],
})


def _mock_model_result(response_text: str) -> MagicMock:
    m = MagicMock(spec=ModelRouterResult)
    m.decision = "LOCAL"
    m.response_text = response_text
    m.primary_audit_code = "LOCAL_COMPLETED"
    m.escalation_trigger_code = None
    m.blocked_external = False
    m.blocked_reason_code = None
    m.calibrated_confidence = 0.85
    m.local_adapter_raw_confidence = 0.85
    m.signal_breakdown = {}
    m.token_optimization = {}
    m.local_model_profile_id = "test_profile"
    m.external_model_id = None
    m.optimized_prompt = None
    m.as_trace_dict.return_value = {
        "decision": "LOCAL", "primary_audit_code": "LOCAL_COMPLETED",
        "escalation_trigger_code": None, "blocked_external": False,
        "blocked_reason_code": None, "calibrated_confidence": 0.85,
        "local_adapter_raw_confidence": 0.85, "signal_breakdown": {},
        "token_optimization": {}, "response_preview": response_text[:500],
        "local_model_profile_id": "test_profile", "external_model_id": None,
    }
    return m


# ── _parse_reviewer_output unit tests ─────────────────────────────────────────

def test_parse_accept_output() -> None:
    out = _parse_reviewer_output(ACCEPT_JSON)
    assert out.recommendation == "ACCEPT"
    assert out.confidence == 0.92
    assert out.findings == []


def test_parse_reject_output() -> None:
    out = _parse_reviewer_output(REJECT_JSON)
    assert out.recommendation == "REJECT"
    assert len(out.findings) == 1
    assert out.findings[0].severity == "BLOCKING"


def test_parse_needs_changes_output() -> None:
    out = _parse_reviewer_output(NEEDS_CHANGES_JSON)
    assert out.recommendation == "NEEDS_CHANGES"
    assert len(out.findings) == 1


def test_parse_missing_recommendation_fails() -> None:
    data = json.loads(ACCEPT_JSON)
    del data["recommendation"]
    with pytest.raises(ReviewerOutputParseError) as ei:
        _parse_reviewer_output(json.dumps(data))
    assert "recommendation" in str(ei.value)


def test_parse_invalid_recommendation_fails() -> None:
    data = json.loads(ACCEPT_JSON)
    data["recommendation"] = "MAYBE"
    with pytest.raises(ReviewerOutputParseError) as ei:
        _parse_reviewer_output(json.dumps(data))
    assert "invalid_recommendation" in str(ei.value)


def test_parse_confidence_out_of_range_fails() -> None:
    data = json.loads(ACCEPT_JSON)
    data["confidence"] = 1.5
    with pytest.raises(ReviewerOutputParseError) as ei:
        _parse_reviewer_output(json.dumps(data))
    assert "out_of_range" in str(ei.value)


def test_parse_reject_without_findings_fails() -> None:
    data = json.loads(REJECT_JSON)
    data["findings"] = []
    with pytest.raises(ReviewerOutputParseError) as ei:
        _parse_reviewer_output(json.dumps(data))
    assert "findings_required" in str(ei.value)


def test_parse_absolute_path_in_finding_fails() -> None:
    data = json.loads(REJECT_JSON)
    data["findings"][0]["path"] = "/etc/passwd"
    with pytest.raises(ReviewerOutputParseError) as ei:
        _parse_reviewer_output(json.dumps(data))
    assert "absolute_path" in str(ei.value)


def test_parse_traversal_path_in_finding_fails() -> None:
    data = json.loads(REJECT_JSON)
    data["findings"][0]["path"] = "../../secret"
    with pytest.raises(ReviewerOutputParseError) as ei:
        _parse_reviewer_output(json.dumps(data))
    assert "traversal" in str(ei.value)


def test_parse_invalid_json_fails() -> None:
    with pytest.raises(ReviewerOutputParseError):
        _parse_reviewer_output("not json")


def test_parse_json_in_fence() -> None:
    fenced = "Review:\n```json\n" + ACCEPT_JSON + "\n```\n"
    out = _parse_reviewer_output(fenced)
    assert out.recommendation == "ACCEPT"


# ── API endpoint tests ─────────────────────────────────────────────────────────

def test_reviewer_requires_auth(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    r = client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={})
    assert r.status_code == 401


def test_viewer_cannot_run_reviewer(client, minimal_project_ids, db_session) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    email = f"viewer-rev-{uid}@example.com"
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
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    lr = client.post("/api/v1/auth/login", json={"email": email, "password": "viewerpass!"})
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=vh)
    assert r.status_code == 403


def test_closed_directive_blocks_reviewer(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    pid = _pid(minimal_project_ids)
    # Accept patch, then close directive
    client.post(f"/api/v1/projects/{pid}/directives/{did}/patches/{patch_id}/accept", headers=h)
    cv = client.post(f"/api/v1/projects/{pid}/directives/{did}/validations",
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
                json={"passed": True, "result_summary": "OK"}, headers=h)
    client.post(f"/api/v1/directives/{did}/signoff", headers=h)
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(ACCEPT_JSON)):
        r = client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    assert r.status_code in (409, 422)
    assert "closed" in r.json()["detail"].lower()


def test_non_proposed_patch_blocks_reviewer(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    pid = _pid(minimal_project_ids)
    # Accept the patch — now it's ACCEPTED, not PROPOSED
    client.post(f"/api/v1/projects/{pid}/directives/{did}/patches/{patch_id}/accept", headers=h)
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(ACCEPT_JSON)):
        r = client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    assert r.status_code in (409, 422)
    assert "proposed" in r.json()["detail"].lower()


def test_wrong_project_directive_rejected(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    wrong_pid = str(uuid.uuid4())
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(ACCEPT_JSON)):
        r = client.post(
            f"/api/v1/projects/{wrong_pid}/directives/{did}/patches/{patch_id}/agents/reviewer/run",
            json={}, headers=h,
        )
    assert r.status_code in (403, 404, 422)


def test_valid_accept_review_creates_record(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(ACCEPT_JSON)):
        r = client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["recommendation"] == "ACCEPT"
    assert body["confidence"] == 0.92
    assert uuid.UUID(body["review_id"])
    db_session.expire_all()
    review = db_session.get(PatchReview, uuid.UUID(body["review_id"]))
    assert review is not None
    assert review.recommendation == ReviewerRecommendation.ACCEPT.value


def test_valid_reject_review_creates_record(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(REJECT_JSON)):
        r = client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["recommendation"] == "REJECT"
    assert len(body["findings"]) == 1
    assert body["findings"][0]["severity"] == "BLOCKING"


def test_valid_needs_changes_creates_record(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(NEEDS_CHANGES_JSON)):
        r = client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["recommendation"] == "NEEDS_CHANGES"


def test_reviewer_does_not_mutate_patch_status(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(ACCEPT_JSON)):
        client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    db_session.expire_all()
    patch_row = db_session.get(PatchProposal, uuid.UUID(patch_id))
    assert patch_row is not None
    assert patch_row.status == PatchProposalStatus.PROPOSED.value  # unchanged!
    assert patch_row.accepted_at is None


def test_invalid_json_returns_422(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result("Not JSON")):
        r = client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    assert r.status_code == 422
    assert "reviewer_output_invalid" in r.json()["detail"]


def test_invalid_confidence_returns_422(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    bad = json.loads(ACCEPT_JSON)
    bad["confidence"] = 2.5
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(json.dumps(bad))):
        r = client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    assert r.status_code == 422


def test_audit_events_emitted(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(ACCEPT_JSON)):
        client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    db_session.expire_all()
    started = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.AGENT_REVIEW_STARTED.value)
    ).first()
    completed = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.AGENT_REVIEW_COMPLETED.value)
    ).first()
    assert started is not None
    assert completed is not None
    p = completed.event_payload_json
    assert p["recommendation"] == "ACCEPT"
    assert p["patch_id"] == patch_id


def test_no_file_contents_in_audit(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    patch_id = _create_proposed_patch(client, minimal_project_ids, did, h)
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(ACCEPT_JSON)):
        client.post(_reviewer_url(minimal_project_ids, did, patch_id), json={}, headers=h)
    db_session.expire_all()
    completed = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.AGENT_REVIEW_COMPLETED.value)
    ).first()
    assert completed is not None
    serialized = json.dumps(completed.event_payload_json)
    assert "import logging" not in serialized  # file content from patch not in audit
