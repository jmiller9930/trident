"""TRIDENT_IMPLEMENTATION_DIRECTIVE_PATCH_002 — patch execution → git commit."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.api.deps.git_deps import get_git_provider
from app.git_provider.base import BranchInfo, CommitInfo, GitProvider, GitProviderError, RepoInfo
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.patch_proposal import PatchExecutionStatus, PatchProposal, PatchProposalStatus
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


# ── Fixtures / helpers ────────────────────────────────────────────────────────

COMMIT_SHA = "cafebabe12345678cafebabe12345678cafebabe"
BRANCH_SHA = "aabbcc1100000000000000000000000000001234"

FAKE_REPO = RepoInfo(
    provider="github",
    owner="acme",
    repo_name="trident-proj",
    clone_url="https://github.com/acme/trident-proj.git",
    html_url="https://github.com/acme/trident-proj",
    default_branch="main",
    private=True,
    created=False,
)


def _mock_provider(push_sha: str = COMMIT_SHA) -> MagicMock:
    m = MagicMock(spec=GitProvider)
    m.provider_name = "github"
    m.link_repo.return_value = FAKE_REPO
    m.get_default_branch_sha.return_value = BRANCH_SHA
    m.create_branch.return_value = BranchInfo(
        provider="github",
        branch_name="trident/aaaabbbb/test-directive",
        commit_sha=BRANCH_SHA,
    )
    m.push_files.return_value = CommitInfo(
        provider="github",
        sha=push_sha,
        message="trident: Test directive",
        branch_name="trident/aaaabbbb/test-directive",
        html_url=f"https://github.com/acme/trident-proj/commit/{push_sha}",
    )
    return m


def _login(client, ids) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(ids) -> str:
    return str(ids["project_id"])


def _override(client, provider):
    client.app.dependency_overrides[get_git_provider] = lambda: provider


def _clear(client):
    client.app.dependency_overrides.pop(get_git_provider, None)


def _make_directive(db_session, ids) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Test directive",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


_VALID_FILES = [
    {"path": "src/module.py", "content": "def hello(): pass\n", "change_type": "update"},
    {"path": "README.md", "content": "# Updated\n", "change_type": "update"},
]

_PATCH_BODY = {
    "title": "Test patch",
    "summary": "Add hello module",
    "files_changed": {"files": _VALID_FILES},
    "unified_diff": "--- a/src/module.py\n+++ b/src/module.py\n@@ -1 +1 @@\n+def hello(): pass",
}


def _patch_url(ids, did, patch_id=None, action=None) -> str:
    pid = _pid(ids)
    base = f"/api/v1/projects/{pid}/directives/{did}/patches"
    if patch_id is None:
        return base
    url = f"{base}/{patch_id}"
    return f"{url}/{action}" if action else url


def _setup_accepted_patch(client, ids, db_session, provider):
    """Link repo, create directive, create branch, create patch, accept it."""
    h = _login(client, ids)
    pid = _pid(ids)
    _override(client, provider)
    # Link repo
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-proj.git"}, headers=h)
    # Create directive + branch
    did = _make_directive(db_session, ids)
    client.post(f"/api/v1/projects/{pid}/git/create-branch",
                json={"directive_id": str(did)}, headers=h)
    # Create patch
    cp = client.post(_patch_url(ids, did), json=_PATCH_BODY, headers=h)
    assert cp.status_code == 201, cp.text
    patch_id = cp.json()["id"]
    # Accept patch
    ar = client.post(_patch_url(ids, did, patch_id, "accept"), headers=h)
    assert ar.status_code == 200, ar.text
    _clear(client)
    return did, patch_id, h


# ── RBAC ─────────────────────────────────────────────────────────────────────

def test_execute_requires_admin(client, minimal_project_ids, db_session) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    provider = _mock_provider()
    did, patch_id, _ = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    uid = uuid.uuid4()
    ce = f"cont-{uid}@example.com"
    u = User(id=uid, display_name="C", email=ce, role="m", password_hash=hash_password("pass1234!"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(
        project_id=minimal_project_ids["project_id"],
        user_id=uid,
        role=ProjectMemberRole.CONTRIBUTOR.value,
    ))
    db_session.commit()
    _override(client, provider)
    lr = client.post("/api/v1/auth/login", json={"email": ce, "password": "pass1234!"})
    ch = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=ch)
    assert r.status_code == 403
    _clear(client)


# ── Status guards ─────────────────────────────────────────────────────────────

def test_execute_proposed_patch_fails(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    _override(client, provider)
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-proj.git"}, headers=h)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(f"/api/v1/projects/{pid}/git/create-branch",
                json={"directive_id": str(did)}, headers=h)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_PATCH_BODY, headers=h)
    patch_id = cp.json()["id"]
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r.status_code == 409
    assert "patch_not_accepted" in r.json()["detail"].lower()
    _clear(client)


def test_execute_rejected_patch_fails(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    _override(client, provider)
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-proj.git"}, headers=h)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(f"/api/v1/projects/{pid}/git/create-branch",
                json={"directive_id": str(did)}, headers=h)
    cp = client.post(_patch_url(minimal_project_ids, did), json=_PATCH_BODY, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id, "reject"),
                json={"reason": "bad"}, headers=h)
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r.status_code == 409
    assert "patch_not_accepted" in r.json()["detail"].lower()
    _clear(client)


# ── Happy path ────────────────────────────────────────────────────────────────

def test_execute_accepted_patch_succeeds(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, patch_id, h = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["commit_sha"] == COMMIT_SHA
    assert body["execution_status"] == PatchExecutionStatus.EXECUTED.value
    assert body["branch_name"] is not None
    _clear(client)


def test_execute_patch_updates_proposal_fields(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, patch_id, h = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    db_session.expire_all()
    row = db_session.get(PatchProposal, uuid.UUID(patch_id))
    assert row is not None
    assert row.execution_status == PatchExecutionStatus.EXECUTED.value
    assert row.execution_commit_sha == COMMIT_SHA
    assert row.executed_at is not None
    assert row.executed_by_user_id == minimal_project_ids["user_id"]
    _clear(client)


def test_execute_returns_proof_object_id(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, patch_id, h = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    body = r.json()
    assert body["proof_object_id"] is not None
    _clear(client)


def test_execute_calls_push_files_with_correct_content(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, patch_id, h = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    provider.push_files.assert_called_once()
    kwargs = provider.push_files.call_args.kwargs
    assert "src/module.py" in kwargs["files"]
    assert "README.md" in kwargs["files"]
    assert kwargs["files"]["src/module.py"] == "def hello(): pass\n"
    _clear(client)


# ── Duplicate execution guard ─────────────────────────────────────────────────

def test_execute_twice_returns_409(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, patch_id, h = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    r2 = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r2.status_code == 409
    assert "patch_already_executed" in r2.json()["detail"]
    _clear(client)


# ── Branch / repo guards ──────────────────────────────────────────────────────

def test_execute_without_branch_returns_409(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    _override(client, provider)
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-proj.git"}, headers=h)
    did = _make_directive(db_session, minimal_project_ids)
    # No create-branch
    cp = client.post(_patch_url(minimal_project_ids, did), json=_PATCH_BODY, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id, "accept"), headers=h)
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r.status_code == 409
    assert "directive_branch_missing" in r.json()["detail"]
    _clear(client)


# ── File validation ───────────────────────────────────────────────────────────

def test_execute_rejects_delete_operation(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    _override(client, provider)
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-proj.git"}, headers=h)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(f"/api/v1/projects/{pid}/git/create-branch",
                json={"directive_id": str(did)}, headers=h)
    delete_body = {
        **_PATCH_BODY,
        "files_changed": {"files": [{"path": "old.py", "content": "", "change_type": "delete"}]},
    }
    cp = client.post(_patch_url(minimal_project_ids, did), json=delete_body, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id, "accept"), headers=h)
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r.status_code == 422
    assert "delete" in r.json()["detail"]
    _clear(client)


def test_execute_rejects_absolute_path(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    _override(client, provider)
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-proj.git"}, headers=h)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(f"/api/v1/projects/{pid}/git/create-branch",
                json={"directive_id": str(did)}, headers=h)
    abs_body = {
        **_PATCH_BODY,
        "files_changed": {"files": [{"path": "/etc/shadow", "content": "x", "change_type": "create"}]},
    }
    cp = client.post(_patch_url(minimal_project_ids, did), json=abs_body, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id, "accept"), headers=h)
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r.status_code == 422
    assert "absolute_path" in r.json()["detail"]
    _clear(client)


def test_execute_rejects_traversal_path(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    _override(client, provider)
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-proj.git"}, headers=h)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(f"/api/v1/projects/{pid}/git/create-branch",
                json={"directive_id": str(did)}, headers=h)
    trav_body = {
        **_PATCH_BODY,
        "files_changed": {"files": [{"path": "../secrets.txt", "content": "x", "change_type": "update"}]},
    }
    cp = client.post(_patch_url(minimal_project_ids, did), json=trav_body, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id, "accept"), headers=h)
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r.status_code == 422
    assert "traversal" in r.json()["detail"]
    _clear(client)


def test_execute_rejects_missing_files_changed(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    _override(client, provider)
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-proj.git"}, headers=h)
    did = _make_directive(db_session, minimal_project_ids)
    client.post(f"/api/v1/projects/{pid}/git/create-branch",
                json={"directive_id": str(did)}, headers=h)
    no_files_body = {"title": "No files", "summary": None}
    cp = client.post(_patch_url(minimal_project_ids, did), json=no_files_body, headers=h)
    patch_id = cp.json()["id"]
    client.post(_patch_url(minimal_project_ids, did, patch_id, "accept"), headers=h)
    r = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r.status_code == 422
    _clear(client)


# ── Audit ─────────────────────────────────────────────────────────────────────

def test_execute_emits_patch_executed_audit(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, patch_id, h = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.PATCH_EXECUTED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert p["commit_sha"] == COMMIT_SHA
    assert p["patch_id"] == patch_id
    # No file contents
    assert "def hello" not in json.dumps(p)
    assert "content" not in json.dumps(p)
    _clear(client)


def test_execute_failure_emits_failed_audit(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, patch_id, h = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    provider.push_files.side_effect = GitProviderError("fail", reason_code="github_api_error")
    _override(client, provider)
    client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(
            AuditEvent.event_type == AuditEventType.PATCH_EXECUTION_FAILED.value
        )
    ).first()
    assert row is not None
    assert row.event_payload_json["patch_id"] == patch_id
    _clear(client)


def test_execute_failure_sets_execution_status_failed(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, patch_id, h = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    provider.push_files.side_effect = GitProviderError("fail", reason_code="github_api_error")
    _override(client, provider)
    client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    db_session.expire_all()
    row = db_session.get(PatchProposal, uuid.UUID(patch_id))
    assert row is not None
    assert row.execution_status == PatchExecutionStatus.FAILED.value
    assert row.execution_commit_sha is None
    _clear(client)


def test_retry_allowed_after_failed_no_commit(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, patch_id, h = _setup_accepted_patch(client, minimal_project_ids, db_session, provider)
    # First attempt fails
    provider.push_files.side_effect = GitProviderError("fail", reason_code="github_api_error")
    _override(client, provider)
    r1 = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r1.status_code in (400, 409, 500, 502)
    # Retry with working provider
    provider.push_files.side_effect = None
    r2 = client.post(_patch_url(minimal_project_ids, did, patch_id, "execute"), headers=h)
    assert r2.status_code == 201, r2.text
    assert r2.json()["commit_sha"] == COMMIT_SHA
    _clear(client)
