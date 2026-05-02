"""TRIDENT_AGENT_RUNTIME_001 — governed Engineer agent runtime."""

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
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.services.agent_runtime_service import (
    AgentOutputParseError,
    AgentRuntimeBlockedError,
    AgentRuntimeService,
    _parse_agent_output,
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
        title="Agent runtime test directive",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    client.post(f"/api/v1/directives/{d.id}/issue", headers=h)
    db_session.expire_all()
    return d.id, h


def _agent_url(ids, did) -> str:
    return f"/api/v1/projects/{_pid(ids)}/directives/{did}/agents/engineer/run"


import base64 as _b64

_CONTENT = "def login(email: str, password: str):\n    if not email or len(password) < 8:\n        raise ValueError('invalid')\n"
_CONTENT_B64 = _b64.b64encode(_CONTENT.encode()).decode()

# New D6-safe contract (base64)
VALID_JSON_RESPONSE = json.dumps({
    "title": "Add input validation to login",
    "summary": "Validates email and password length before DB query.",
    "files": [
        {
            "path": "app/auth/login.py",
            "change_type": "update",
            "content_base64": _CONTENT_B64,
        }
    ],
})

# Legacy contract still supported (backward compat)
VALID_JSON_RESPONSE_LEGACY = json.dumps({
    "title": "Add input validation to login",
    "summary": "Validates email and password length before DB query.",
    "files_changed": [
        {
            "path": "app/auth/login.py",
            "change_type": "update",
            "content": _CONTENT,
        }
    ],
    "unified_diff": "",
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
        "decision": "LOCAL",
        "primary_audit_code": "LOCAL_COMPLETED",
        "escalation_trigger_code": None,
        "blocked_external": False,
        "blocked_reason_code": None,
        "calibrated_confidence": 0.85,
        "local_adapter_raw_confidence": 0.85,
        "signal_breakdown": {},
        "token_optimization": {},
        "response_preview": response_text[:500],
        "local_model_profile_id": "test_profile",
        "external_model_id": None,
    }
    return m


# ── _parse_agent_output unit tests ────────────────────────────────────────────

def test_parse_valid_json_output_b64() -> None:
    """New D6-safe contract: files + content_base64."""
    out = _parse_agent_output(VALID_JSON_RESPONSE)
    assert out.title == "Add input validation to login"
    assert len(out.files_changed) == 1
    assert out.files_changed[0]["path"] == "app/auth/login.py"
    # Content is decoded from base64
    assert "def login" in out.files_changed[0]["content"]


def test_parse_legacy_contract_still_works() -> None:
    """Legacy files_changed + content still accepted."""
    out = _parse_agent_output(VALID_JSON_RESPONSE_LEGACY)
    assert out.title == "Add input validation to login"
    assert out.files_changed[0]["content"] == _CONTENT


def test_parse_json_in_fence() -> None:
    fenced = "Here is the patch:\n```json\n" + VALID_JSON_RESPONSE + "\n```\n"
    out = _parse_agent_output(fenced)
    assert out.title == "Add input validation to login"


def test_parse_missing_title_fails() -> None:
    data = json.loads(VALID_JSON_RESPONSE)
    del data["title"]
    with pytest.raises(AgentOutputParseError) as ei:
        _parse_agent_output(json.dumps(data))
    assert "title" in str(ei.value)


def test_parse_empty_files_fails() -> None:
    data = json.loads(VALID_JSON_RESPONSE)
    data["files"] = []
    with pytest.raises(AgentOutputParseError):
        _parse_agent_output(json.dumps(data))


def test_parse_absolute_path_fails() -> None:
    data = json.loads(VALID_JSON_RESPONSE)
    data["files"][0]["path"] = "/etc/passwd"
    with pytest.raises(AgentOutputParseError) as ei:
        _parse_agent_output(json.dumps(data))
    assert "absolute_path" in str(ei.value)


def test_parse_traversal_path_fails() -> None:
    data = json.loads(VALID_JSON_RESPONSE)
    data["files"][0]["path"] = "../secret.txt"
    with pytest.raises(AgentOutputParseError) as ei:
        _parse_agent_output(json.dumps(data))
    assert "traversal" in str(ei.value)


def test_parse_delete_operation_fails() -> None:
    data = json.loads(VALID_JSON_RESPONSE)
    data["files"][0]["change_type"] = "delete"
    with pytest.raises(AgentOutputParseError) as ei:
        _parse_agent_output(json.dumps(data))
    assert "delete" in str(ei.value)


def test_parse_bad_base64_fails() -> None:
    data = json.loads(VALID_JSON_RESPONSE)
    data["files"][0]["content_base64"] = "!!! not base64 !!!"
    with pytest.raises(AgentOutputParseError) as ei:
        _parse_agent_output(json.dumps(data))
    assert "base64" in str(ei.value)


def test_parse_invalid_json_fails() -> None:
    with pytest.raises(AgentOutputParseError):
        _parse_agent_output("not json at all !!!!")


# ── API endpoint tests ────────────────────────────────────────────────────────

def test_run_requires_auth(client, minimal_project_ids, db_session) -> None:
    did, _ = _make_issued_directive(client, db_session, minimal_project_ids)
    r = client.post(_agent_url(minimal_project_ids, did), json={})
    assert r.status_code == 401


def test_viewer_cannot_run_engineer(client, minimal_project_ids, db_session) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    email = f"viewer-ar-{uid}@example.com"
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
    r = client.post(_agent_url(minimal_project_ids, did), json={}, headers=vh)
    assert r.status_code == 403


def test_closed_directive_blocks_run(client, minimal_project_ids, db_session) -> None:
    from app.models.directive import Directive
    from app.models.enums import DirectiveStatus

    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    # Close it
    cv = client.post(f"/api/v1/projects/{pid}/directives/{did}/validations",
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
                json={"passed": True, "result_summary": "OK"}, headers=h)
    client.post(f"/api/v1/directives/{did}/signoff", headers=h)
    db_session.expire_all()

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(VALID_JSON_RESPONSE)):
        r = client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)
    assert r.status_code in (409, 422)
    assert "closed" in r.json()["detail"].lower()


def test_draft_directive_blocks_run(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Draft directive",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    # Do NOT issue — stays DRAFT

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(VALID_JSON_RESPONSE)):
        r = client.post(_agent_url(minimal_project_ids, str(d.id)), json={}, headers=h)
    assert r.status_code in (409, 422)
    assert "issued" in r.json()["detail"].lower()


def test_valid_output_creates_proposed_patch(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(VALID_JSON_RESPONSE)):
        r = client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PROPOSED"
    assert body["title"] == "Add input validation to login"
    assert uuid.UUID(body["patch_id"])

    db_session.expire_all()
    patch_row = db_session.get(PatchProposal, uuid.UUID(body["patch_id"]))
    assert patch_row is not None
    assert patch_row.status == PatchProposalStatus.PROPOSED.value
    assert patch_row.proposed_by_agent_role == "ENGINEER"


def test_invalid_json_returns_422(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result("This is not JSON at all.")):
        r = client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)

    assert r.status_code == 422
    assert "agent_output_invalid" in r.json()["detail"]


def test_missing_required_field_returns_422(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    bad = json.loads(VALID_JSON_RESPONSE)
    del bad["files"]

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(json.dumps(bad))):
        r = client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)

    assert r.status_code == 422


def test_absolute_path_in_response_returns_422(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    bad = json.loads(VALID_JSON_RESPONSE)
    bad["files"][0]["path"] = "/etc/hosts"

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(json.dumps(bad))):
        r = client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)

    assert r.status_code == 422


def test_traversal_path_in_response_returns_422(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    bad = json.loads(VALID_JSON_RESPONSE)
    bad["files"][0]["path"] = "../../secret"

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(json.dumps(bad))):
        r = client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)

    assert r.status_code == 422


def test_delete_operation_rejected(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)
    bad = json.loads(VALID_JSON_RESPONSE)
    bad["files"][0]["change_type"] = "delete"

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(json.dumps(bad))):
        r = client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)

    assert r.status_code == 422


def test_audit_events_emitted(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(VALID_JSON_RESPONSE)):
        client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)

    db_session.expire_all()
    started = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.AGENT_RUN_STARTED.value)
    ).first()
    completed = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.AGENT_RUN_COMPLETED.value)
    ).first()
    assert started is not None
    assert completed is not None
    assert completed.event_payload_json["agent_role"] == "ENGINEER"


def test_no_file_contents_in_audit(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(VALID_JSON_RESPONSE)):
        client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)

    db_session.expire_all()
    completed = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.AGENT_RUN_COMPLETED.value)
    ).first()
    assert completed is not None
    import json as _json
    serialized = _json.dumps(completed.event_payload_json)
    assert "def login" not in serialized  # file content not in audit


def test_patch_is_proposed_not_accepted(client, minimal_project_ids, db_session) -> None:
    did, h = _make_issued_directive(client, db_session, minimal_project_ids)

    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(VALID_JSON_RESPONSE)):
        r = client.post(_agent_url(minimal_project_ids, did), json={}, headers=h)

    patch_row = db_session.get(PatchProposal, uuid.UUID(r.json()["patch_id"]))
    assert patch_row is not None
    assert patch_row.status == PatchProposalStatus.PROPOSED.value
    # Must NOT be accepted, executed, or closed
    from app.models.patch_proposal import PatchExecutionStatus
    assert patch_row.execution_status == PatchExecutionStatus.NOT_EXECUTED.value
    assert patch_row.accepted_at is None
    assert patch_row.accepted_by_user_id is None
