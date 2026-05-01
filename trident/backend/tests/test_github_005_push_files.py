"""TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_005 — push files to directive branch."""

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
from app.models.git_branch_log import GitBranchLog
from app.models.project import Project
from app.models.proof_object import ProofObject
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


# ── Fixtures / helpers ────────────────────────────────────────────────────────

SHA = "cafebabe00000000000000000000000000cafe01"
COMMIT_SHA = "deadbeef00000000000000000000000000dead01"

FAKE_REPO = RepoInfo(
    provider="github",
    owner="acme",
    repo_name="trident-project",
    clone_url="https://github.com/acme/trident-project.git",
    html_url="https://github.com/acme/trident-project",
    default_branch="main",
    private=True,
    created=False,
)


def _mock_provider() -> MagicMock:
    m = MagicMock(spec=GitProvider)
    m.provider_name = "github"
    m.link_repo.return_value = FAKE_REPO
    m.get_default_branch_sha.return_value = SHA
    m.create_branch.return_value = BranchInfo(
        provider="github",
        branch_name="trident/aaaabbbb/add-feature",
        commit_sha=SHA,
    )
    m.push_files.return_value = CommitInfo(
        provider="github",
        sha=COMMIT_SHA,
        message="chore: Trident push",
        branch_name="trident/aaaabbbb/add-feature",
        html_url=f"https://github.com/acme/trident-project/commit/{COMMIT_SHA}",
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


def _create_directive(db_session, ids) -> tuple[uuid.UUID, str]:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Add feature Z",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id, d.title


def _link_and_branch(client, ids, db_session, provider):
    """Link repo + create branch so push-files has something to push to."""
    h = _login(client, ids)
    pid = _pid(ids)
    _override(client, provider)
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-project.git"}, headers=h)
    did, title = _create_directive(db_session, ids)
    client.post(f"/api/v1/projects/{pid}/git/create-branch",
                json={"directive_id": str(did)}, headers=h)
    _clear(client)
    return did, h


# ── RBAC ─────────────────────────────────────────────────────────────────────

def test_push_files_requires_contributor(client, minimal_project_ids, db_session) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    ve = f"viewer-005-{uid}@example.com"
    u = User(id=uid, display_name="V", email=ve, role="member",
             password_hash=hash_password("viewerpass!"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(
        project_id=minimal_project_ids["project_id"],
        user_id=uid,
        role=ProjectMemberRole.VIEWER.value,
    ))
    db_session.commit()

    provider = _mock_provider()
    _override(client, provider)
    lr = client.post("/api/v1/auth/login", json={"email": ve, "password": "viewerpass!"})
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    pid = _pid(minimal_project_ids)
    did = str(uuid.uuid4())
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "README.md", "content": "hi"}], "commit_message": "x"},
        headers=vh,
    )
    assert r.status_code == 403
    _clear(client)


# ── Guard: missing repo / branch ──────────────────────────────────────────────

def test_push_files_404_when_no_repo_linked(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    _override(client, provider)
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    did = str(uuid.uuid4())
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "a.py", "content": "x"}], "commit_message": "m"},
        headers=h,
    )
    assert r.status_code in (404, 422)
    _clear(client)


def test_push_files_409_when_branch_not_created(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    _override(client, provider)
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    client.post(f"/api/v1/projects/{pid}/git/link-repo",
                json={"clone_url": "https://github.com/acme/trident-project.git"}, headers=h)
    did, _ = _create_directive(db_session, minimal_project_ids)
    # No create-branch call
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{str(did)}/push-files",
        json={"files": [{"path": "a.py", "content": "x"}], "commit_message": "m"},
        headers=h,
    )
    assert r.status_code == 409
    assert "directive_branch_missing" in r.json()["detail"]
    _clear(client)


def test_push_files_422_directive_project_mismatch(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    wrong_did = str(uuid.uuid4())
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{wrong_did}/push-files",
        json={"files": [{"path": "a.py", "content": "x"}], "commit_message": "m"},
        headers=h,
    )
    assert r.status_code == 422
    assert "directive_not_in_project" in r.json()["detail"]
    _clear(client)


# ── Input validation ──────────────────────────────────────────────────────────

def test_push_files_422_absolute_path(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "/etc/passwd", "content": "x"}], "commit_message": "m"},
        headers=h,
    )
    assert r.status_code == 422
    _clear(client)


def test_push_files_422_traversal_path(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "../secret.txt", "content": "x"}], "commit_message": "m"},
        headers=h,
    )
    assert r.status_code == 422
    _clear(client)


def test_push_files_422_empty_files(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [], "commit_message": "m"},
        headers=h,
    )
    assert r.status_code == 422
    _clear(client)


def test_push_files_422_blank_commit_message(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "a.py", "content": "x"}], "commit_message": ""},
        headers=h,
    )
    assert r.status_code == 422
    _clear(client)


# ── Happy path ────────────────────────────────────────────────────────────────

def test_push_files_success_response(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={
            "files": [
                {"path": "src/module.py", "content": "def hello(): pass"},
                {"path": "README.md", "content": "# Updated"},
            ],
            "commit_message": "feat: add module",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["commit_sha"] == COMMIT_SHA
    assert body["file_count"] == 2
    assert body["branch_name"] is not None
    assert body["provider"] == "github"
    assert "token" not in r.text.lower()
    _clear(client)


def test_push_files_persists_branch_log_commit_pushed(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "f.py", "content": "x"}], "commit_message": "push test"},
        headers=h,
    )
    db_session.expire_all()
    row = db_session.scalars(
        select(GitBranchLog).where(
            GitBranchLog.directive_id == did,
            GitBranchLog.event_type == "commit_pushed",
        )
    ).first()
    assert row is not None
    assert row.commit_sha == COMMIT_SHA
    assert row.commit_message == "push test"
    _clear(client)


def test_push_files_updates_project_git_commit_sha(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "f.py", "content": "x"}], "commit_message": "sha test"},
        headers=h,
    )
    db_session.expire_all()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    assert proj.git_commit_sha == COMMIT_SHA
    _clear(client)


def test_push_files_emits_git_commit_pushed_audit(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "src/app.py", "content": "x"}], "commit_message": "audit test"},
        headers=h,
    )
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.GIT_COMMIT_PUSHED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert p["file_count"] == 1
    assert p["commit_sha"] == COMMIT_SHA
    assert "token" not in json.dumps(p)
    # File contents MUST NOT appear in audit
    assert "x" != p.get("content")
    assert "content" not in json.dumps(p)
    _clear(client)


def test_push_files_creates_proof_object(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "f.py", "content": "x"}], "commit_message": "proof test"},
        headers=h,
    )
    body = r.json()
    assert body["proof_object_id"] is not None
    db_session.expire_all()
    proof = db_session.get(ProofObject, uuid.UUID(body["proof_object_id"]))
    assert proof is not None
    assert proof.proof_type == "GIT_COMMIT_PUSHED"
    assert proof.proof_hash == COMMIT_SHA
    _clear(client)


def test_push_files_provider_error_maps_to_502(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    provider.push_files.side_effect = GitProviderError("push failed", reason_code="github_api_error")
    did, h = _link_and_branch(client, minimal_project_ids, db_session, _mock_provider())
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "f.py", "content": "x"}], "commit_message": "m"},
        headers=h,
    )
    assert r.status_code == 502
    _clear(client)


def test_push_files_no_token_in_response(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={"files": [{"path": "f.py", "content": "x"}], "commit_message": "m"},
        headers=h,
    )
    for marker in ("github_pat_", "ghp_", "Bearer github"):
        assert marker not in r.text
    _clear(client)


def test_push_files_provider_called_with_correct_args(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    did, h = _link_and_branch(client, minimal_project_ids, db_session, provider)
    _override(client, provider)
    pid = _pid(minimal_project_ids)
    client.post(
        f"/api/v1/projects/{pid}/git/directives/{did}/push-files",
        json={
            "files": [{"path": "src/hello.py", "content": "print('hi')"}],
            "commit_message": "feat: add hello",
        },
        headers=h,
    )
    provider.push_files.assert_called_once()
    kwargs = provider.push_files.call_args.kwargs
    assert "src/hello.py" in kwargs["files"]
    assert kwargs["files"]["src/hello.py"] == "print('hi')"
    assert kwargs["message"] == "feat: add hello"
    _clear(client)
