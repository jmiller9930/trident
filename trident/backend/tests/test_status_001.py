"""TRIDENT_IMPLEMENTATION_DIRECTIVE_STATUS_001 — directive state aggregate endpoint."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

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


def _make_directive(db_session, ids, title="Test directive") -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title=title,
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


def _state_url(ids, did) -> str:
    return f"/api/v1/projects/{_pid(ids)}/directives/{did}/status"


def _mock_provider() -> MagicMock:
    m = MagicMock(spec=GitProvider)
    m.provider_name = "github"
    m.link_repo.return_value = RepoInfo(
        provider="github", owner="acme", repo_name="repo",
        clone_url="https://github.com/acme/repo.git",
        html_url="https://github.com/acme/repo",
        default_branch="main", private=True, created=False,
    )
    m.get_default_branch_sha.return_value = "sha_branch"
    m.create_branch.return_value = BranchInfo(
        provider="github", branch_name="trident/aaaabbbb/test",
        commit_sha="sha_branch",
    )
    m.push_files.return_value = CommitInfo(
        provider="github", sha="sha_commit",
        message="x", branch_name="trident/aaaabbbb/test",
    )
    return m


# ── Basic structure ───────────────────────────────────────────────────────────

def test_status_returns_required_sections(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    r = client.get(_state_url(minimal_project_ids, did), headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    for section in ("directive", "lifecycle_phase", "git", "patches", "validations",
                    "signoff", "allowed_actions", "as_of"):
        assert section in body, f"Missing section: {section}"


def test_status_requires_auth(client, minimal_project_ids, db_session) -> None:
    did = _make_directive(db_session, minimal_project_ids)
    r = client.get(_state_url(minimal_project_ids, did))
    assert r.status_code == 401


def test_status_directive_mismatch_rejected(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    r = client.get(_state_url(minimal_project_ids, str(uuid.uuid4())), headers=h)
    assert r.status_code in (404, 422)


# ── Directive core ────────────────────────────────────────────────────────────

def test_status_directive_section_matches_db(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids, title="My feature")
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["directive"]["title"] == "My feature"
    assert body["directive"]["status"] == DirectiveStatus.DRAFT.value
    assert body["directive"]["id"] == str(did)


def test_lifecycle_phase_draft(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["lifecycle_phase"] == "authoring"


def test_lifecycle_phase_issued(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["lifecycle_phase"] == "active"


def test_lifecycle_phase_closed(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    # Add passed validation
    cv = client.post(
        f"/api/v1/projects/{pid}/directives/{did}/validations",
        json={"validation_type": "MANUAL"}, headers=h,
    )
    vid = cv.json()["id"]
    client.post(
        f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
        json={"passed": True, "result_summary": "OK"}, headers=h,
    )
    client.post(f"/api/v1/directives/{did}/signoff", headers=h)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["lifecycle_phase"] == "done"


# ── Git state ─────────────────────────────────────────────────────────────────

def test_git_repo_not_linked_initially(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["git"]["repo_linked"] is False


def test_git_repo_linked_after_link(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.app.dependency_overrides[get_git_provider] = lambda: provider
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/repo.git"}, headers=h)
    client.app.dependency_overrides.pop(get_git_provider, None)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["git"]["repo_linked"] is True
    assert body["git"]["clone_url"] is not None


def test_git_branch_created_for_directive_reflected(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.app.dependency_overrides[get_git_provider] = lambda: provider
    client.app.dependency_overrides[get_optional_git_provider] = lambda: provider
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/repo.git"}, headers=h)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    client.app.dependency_overrides.pop(get_git_provider, None)
    client.app.dependency_overrides.pop(get_optional_git_provider, None)

    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["git"]["branch_created_for_directive"] is True
    assert body["git"]["directive_branch_name"] is not None


# ── Patch state ───────────────────────────────────────────────────────────────

def test_patches_zero_initially(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["patches"]["total"] == 0


def test_patches_counts_after_create(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    patch_body = {
        "title": "My patch",
        "files_changed": {"files": [{"path": "f.py", "content": "x", "change_type": "update"}]},
    }
    client.post(f"/api/v1/projects/{pid}/directives/{did}/patches", json=patch_body, headers=h)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["patches"]["total"] == 1
    assert body["patches"]["proposed"] == 1
    assert body["patches"]["latest_patch_title"] == "My patch"


# ── Validation state ──────────────────────────────────────────────────────────

def test_validations_zero_initially(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["validations"]["total"] == 0


def test_validations_counts_passed(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    cv = client.post(f"/api/v1/projects/{pid}/directives/{did}/validations",
                     json={"validation_type": "MANUAL"}, headers=h)
    vid = cv.json()["id"]
    client.post(f"/api/v1/projects/{pid}/directives/{did}/validations/{vid}/complete",
                json={"passed": True, "result_summary": "OK"}, headers=h)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["validations"]["passed"] == 1
    assert body["validations"]["latest_run_status"] == "PASSED"


# ── Signoff eligibility ───────────────────────────────────────────────────────

def test_signoff_not_eligible_without_validations(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["signoff"]["eligible"] is False
    assert len(body["signoff"]["blocking_reasons"]) > 0


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
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["signoff"]["eligible"] is True
    assert body["signoff"]["blocking_reasons"] == []


# ── Allowed actions ───────────────────────────────────────────────────────────

def test_allowed_actions_present_in_response(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    action_names = {a["action"] for a in body["allowed_actions"]}
    for expected in ("issue", "create_patch", "create_validation", "signoff"):
        assert expected in action_names


def test_issue_action_enabled_for_draft(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    issue_action = next((a for a in body["allowed_actions"] if a["action"] == "issue"), None)
    assert issue_action is not None
    assert issue_action["enabled"] is True


def test_all_actions_disabled_when_closed(client, minimal_project_ids, db_session) -> None:
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
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    mutating = [a for a in body["allowed_actions"] if a["action"] in
                ("create_patch", "execute_patch", "create_validation", "signoff")]
    for a in mutating:
        assert a["enabled"] is False, f"Expected {a['action']} disabled after closure"


def test_as_of_is_present(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _make_directive(db_session, minimal_project_ids)
    body = client.get(_state_url(minimal_project_ids, did), headers=h).json()
    assert body["as_of"] is not None
