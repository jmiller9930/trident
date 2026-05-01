"""TRIDENT_IMPLEMENTATION_DIRECTIVE_STATUS_001 — execution-state aggregate endpoint."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.api.deps.git_deps import get_git_provider, get_optional_git_provider
from app.git_provider.base import BranchInfo, CommitInfo, GitProvider, RepoInfo
from app.models.enums import DirectiveStatus
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login(client, ids) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(ids) -> str:
    return str(ids["project_id"])


def _make_directive(db_session, ids, title: str = "Exec state test") -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title=title,
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


def _es_url(ids, did) -> str:
    return f"/api/v1/projects/{_pid(ids)}/directives/{did}/execution-state"


def _mock_provider() -> MagicMock:
    m = MagicMock(spec=GitProvider)
    m.provider_name = "github"
    m.link_repo.return_value = RepoInfo(
        provider="github", owner="acme", repo_name="proj",
        clone_url="https://github.com/acme/proj.git",
        html_url="https://github.com/acme/proj",
        default_branch="main", private=True, created=False,
    )
    m.get_default_branch_sha.return_value = "branchsha"
    m.create_branch.return_value = BranchInfo(
        provider="github", branch_name="trident/aaaabbbb/exec-state-test",
        commit_sha="branchsha",
    )
    m.push_files.return_value = CommitInfo(
        provider="github", sha="commitsha",
        message="x", branch_name="trident/aaaabbbb/exec-state-test",
    )
    return m


def _link_and_branch(client, ids, db_session, did, provider) -> None:
    pid = _pid(ids)
    h = _login(client, ids)
    client.app.dependency_overrides[get_git_provider] = lambda: provider
    client.app.dependency_overrides[get_optional_git_provider] = lambda: provider
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/proj.git"}, headers=h)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    client.app.dependency_overrides.pop(get_git_provider, None)
    client.app.dependency_overrides.pop(get_optional_git_provider, None)


# ── Shape ─────────────────────────────────────────────────────────────────────

def test_execution_state_has_all_sections(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    r = client.get(_es_url(minimal_project_ids, did), headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    for section in ("directive", "git", "patch", "validation", "signoff",
                    "actions_allowed", "blocking_reasons", "computed_at"):
        assert section in body, f"Missing section: {section}"


def test_execution_state_directive_section(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids, title="My exec test")
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    d = body["directive"]
    assert d["directive_id"] == str(did)
    assert d["title"] == "My exec test"
    assert d["status"] == DirectiveStatus.DRAFT.value
    assert d["closed_at"] is None


def test_execution_state_actions_allowed_all_present(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    actions = body["actions_allowed"]
    for key in ("create_patch", "accept_patch", "reject_patch", "execute_patch",
                "create_validation", "start_validation", "complete_validation",
                "waive_validation", "signoff"):
        assert key in actions, f"Missing action: {key}"
        assert "allowed" in actions[key]


# ── Auth / RBAC ────────────────────────────────────────────────────────────────

def test_execution_state_requires_auth(client, minimal_project_ids, db_session) -> None:
    did = _make_directive(db_session, minimal_project_ids)
    r = client.get(_es_url(minimal_project_ids, did))
    assert r.status_code == 401


def test_execution_state_wrong_project_rejected(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    wrong_pid = str(uuid.uuid4())
    r = client.get(f"/api/v1/projects/{wrong_pid}/directives/{did}/execution-state", headers=h)
    assert r.status_code in (403, 404, 422)


def test_viewer_can_read_execution_state(client, minimal_project_ids, db_session) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    did = _make_directive(db_session, minimal_project_ids)
    uid = uuid.uuid4()
    email = f"viewer-es-{uid}@example.com"
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
    lr = client.post("/api/v1/auth/login", json={"email": email, "password": "viewerpass!"})
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.get(_es_url(minimal_project_ids, did), headers=vh)
    assert r.status_code == 200


# ── Git state ─────────────────────────────────────────────────────────────────

def test_git_not_linked_initially(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["git"]["repo_linked"] is False
    assert body["git"]["branch_created"] is False
    assert body["git"]["commit_pushed"] is False


def test_git_linked_after_repo_link(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.app.dependency_overrides[get_git_provider] = lambda: provider
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/proj.git"}, headers=h)
    client.app.dependency_overrides.pop(get_git_provider, None)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["git"]["repo_linked"] is True
    assert body["git"]["provider"] == "github"
    assert body["git"]["owner"] == "acme"
    assert body["git"]["repo_name"] == "proj"


def test_git_branch_created_after_issue(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did = _make_directive(db_session, minimal_project_ids)
    _link_and_branch(client, minimal_project_ids, db_session, did, provider)
    h = _login(client, minimal_project_ids)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["git"]["branch_created"] is True
    assert body["git"]["branch_name"] is not None


# ── Patch state ───────────────────────────────────────────────────────────────

def test_patch_counts_zero_initially(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["patch"]["patch_count"] == 0
    assert body["patch"]["accepted_patch_id"] is None
    assert body["patch"]["accepted_patch_executed"] is False


def test_patch_accepted_reflected(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    pb = {"title": "My patch",
          "files_changed": {"files": [{"path": "f.py", "content": "x", "change_type": "update"}]}}
    cp = client.post(f"/api/v1/projects/{pid}/directives/{did}/patches", json=pb, headers=h)
    patch_id = cp.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/patches/{patch_id}/accept", headers=h)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["patch"]["accepted_patch_id"] == patch_id
    assert body["patch"]["accepted_patch_executed"] is False


# ── Validation state ──────────────────────────────────────────────────────────

def test_validation_counts_zero_initially(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["validation"]["validation_count"] == 0
    assert body["validation"]["signoff_eligible"] is False


def test_signoff_eligible_after_passed_validation(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    cv = client.post(f"/api/v1/projects/{pid}/directives/{did}/validations",
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
                json={"passed": True, "result_summary": "OK"}, headers=h)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["validation"]["passed_count"] == 1
    assert body["validation"]["signoff_eligible"] is True


def test_failed_validation_blocks_signoff(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    cv = client.post(f"/api/v1/projects/{pid}/directives/{did}/validations",
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
                json={"passed": False, "result_summary": "FAIL"}, headers=h)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["validation"]["failed_count"] == 1
    assert body["validation"]["signoff_eligible"] is False
    signoff_action = body["actions_allowed"]["signoff"]
    assert signoff_action["allowed"] is False
    assert signoff_action["reason_code"] in ("unwaived_failure", "no_passed_validations")


# ── Actions ───────────────────────────────────────────────────────────────────

def test_execute_patch_blocked_without_repo(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    ep = body["actions_allowed"]["execute_patch"]
    assert ep["allowed"] is False
    assert ep["reason_code"] == "no_repo_linked"


def test_actions_reason_code_on_no_accepted_patch(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did = _make_directive(db_session, minimal_project_ids)
    _link_and_branch(client, minimal_project_ids, db_session, did, provider)
    h = _login(client, minimal_project_ids)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    ep = body["actions_allowed"]["execute_patch"]
    assert ep["allowed"] is False
    assert ep["reason_code"] == "no_accepted_patch"


# ── Closed state ──────────────────────────────────────────────────────────────

def test_closed_directive_disables_all_mutations(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    cv = client.post(f"/api/v1/projects/{pid}/directives/{did}/validations",
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
                json={"passed": True, "result_summary": "OK"}, headers=h)
    client.post(f"/api/v1/directives/{did}/signoff", headers=h)

    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["signoff"]["closed"] is True
    mutating_actions = [
        "create_patch", "accept_patch", "reject_patch", "execute_patch",
        "create_validation", "start_validation", "complete_validation",
        "waive_validation", "signoff",
    ]
    for key in mutating_actions:
        a = body["actions_allowed"][key]
        assert a["allowed"] is False, f"Expected {key} disabled after closure"
        assert a["reason_code"] == "directive_closed", f"Expected reason_code=directive_closed on {key}"


def test_closed_signoff_returns_proof_object_id(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    cv = client.post(f"/api/v1/projects/{pid}/directives/{did}/validations",
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
                json={"passed": True, "result_summary": "OK"}, headers=h)
    client.post(f"/api/v1/directives/{did}/signoff", headers=h)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["signoff"]["proof_object_id"] is not None


# ── Blocking reasons ──────────────────────────────────────────────────────────

def test_blocking_reasons_empty_when_signoff_eligible(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    cv = client.post(f"/api/v1/projects/{pid}/directives/{did}/validations",
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
                json={"passed": True, "result_summary": "OK"}, headers=h)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    assert body["validation"]["signoff_eligible"] is True
    blocking = body["blocking_reasons"]
    signoff_related = [b for b in blocking if "validation" in b["code"] or "passed" in b["code"]]
    assert not signoff_related


def test_blocking_reasons_has_required_next_action(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_es_url(minimal_project_ids, did), headers=h).json()
    blocking = body["blocking_reasons"]
    for b in blocking:
        assert "code" in b
        assert "message" in b
        assert "required_next_action" in b


def test_no_client_supplied_state_accepted(client, minimal_project_ids, db_session) -> None:
    """Endpoint is GET-only — no body accepted."""
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    r = client.get(_es_url(minimal_project_ids, did), headers=h)
    assert r.status_code == 200
