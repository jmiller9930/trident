"""TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_003 — Git API endpoints (mocked provider)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.api.deps.git_deps import get_git_provider
from app.git_provider.base import (
    BranchInfo,
    CommitInfo,
    GitProvider,
    GitProviderConfigError,
    GitProviderDisabledError,
    GitProviderError,
    RepoInfo,
)
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.git_branch_log import GitBranchLog
from app.models.git_repo_link import GitRepoLink
from app.models.project import Project
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


# ── Fixtures ──────────────────────────────────────────────────────────────────

FAKE_REPO = RepoInfo(
    provider="github",
    owner="acme",
    repo_name="my-project",
    clone_url="https://github.com/acme/my-project.git",
    html_url="https://github.com/acme/my-project",
    default_branch="main",
    private=True,
    created=True,
)

FAKE_BRANCH = BranchInfo(
    provider="github",
    branch_name="trident/d3f1a2b4/add-feature",
    commit_sha="abc123def456abc123def456abc123def456abc1",
    html_url="https://github.com/acme/my-project/tree/trident/d3f1a2b4/add-feature",
)

FAKE_COMMIT = CommitInfo(
    provider="github",
    sha="deadbeef0000000000000000000000000000dead",
    message="chore: Trident scaffold initialization",
    branch_name="main",
    html_url="https://github.com/acme/my-project/commit/deadbeef",
)

SHA_MAIN = "0123456789abcdef0123456789abcdef01234567"


def _make_mock_provider(
    *,
    create_repo: RepoInfo = FAKE_REPO,
    link_repo: RepoInfo = FAKE_REPO,
    branch_sha: str = SHA_MAIN,
    branch_info: BranchInfo = FAKE_BRANCH,
    push_commit: CommitInfo = FAKE_COMMIT,
) -> MagicMock:
    mock = MagicMock(spec=GitProvider)
    mock.provider_name = "github"
    mock.create_repo.return_value = create_repo
    mock.link_repo.return_value = link_repo
    mock.get_default_branch_sha.return_value = branch_sha
    mock.create_branch.return_value = branch_info
    mock.push_files.return_value = push_commit
    return mock


def _get_app(client_fixture):
    """Find the FastAPI app from the TestClient instance."""
    return getattr(client_fixture, "app", None)


def _override_provider(client_fixture, mock_provider: MagicMock) -> None:
    app = _get_app(client_fixture)
    if app:
        app.dependency_overrides[get_git_provider] = lambda: mock_provider


def _clear_provider(client_fixture) -> None:
    app = _get_app(client_fixture)
    if app:
        app.dependency_overrides.pop(get_git_provider, None)


@pytest.fixture
def mock_provider() -> MagicMock:
    return _make_mock_provider()


@pytest.fixture
def git_client(client, mock_provider):
    _override_provider(client, mock_provider)
    yield client
    _clear_provider(client)


def _headers(client, minimal_project_ids):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": minimal_project_ids["email"], "password": minimal_project_ids["password"]},
    )
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(minimal_project_ids):
    return str(minimal_project_ids["project_id"])


# ── 503 when GitHub disabled ──────────────────────────────────────────────────

def test_create_repo_503_when_github_disabled(client, minimal_project_ids) -> None:
    """Override with 503-raising dep to simulate disabled GitHub."""
    from fastapi import HTTPException

    def _disabled_dep():
        raise HTTPException(status_code=503, detail="git_provider_disabled")

    app = _get_app(client)
    app.dependency_overrides[get_git_provider] = _disabled_dep
    try:
        h = _headers(client, minimal_project_ids)
        pid = _pid(minimal_project_ids)
        r = client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
        assert r.status_code == 503
        assert "git_provider_disabled" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_git_provider, None)


# ── RBAC checks ───────────────────────────────────────────────────────────────

def test_create_repo_requires_admin(client, minimal_project_ids, db_session, mock_provider) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    viewer_email = f"viewer-{uid}@example.com"
    u = User(id=uid, display_name="Viewer", email=viewer_email, role="member",
             password_hash=hash_password("viewerpass1"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(
        project_id=minimal_project_ids["project_id"],
        user_id=uid,
        role=ProjectMemberRole.VIEWER.value,
    ))
    db_session.commit()

    _override_provider(client, mock_provider)
    lr = client.post("/api/v1/auth/login", json={"email": viewer_email, "password": "viewerpass1"})
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    pid = _pid(minimal_project_ids)
    r = client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=vh)
    assert r.status_code == 403
    _clear_provider(client)


def test_repo_status_requires_viewer(client, minimal_project_ids) -> None:
    r = client.get(f"/api/v1/projects/{_pid(minimal_project_ids)}/git/repo-status")
    assert r.status_code == 401


def test_create_branch_requires_contributor(client, minimal_project_ids, db_session, mock_provider) -> None:
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password

    uid = uuid.uuid4()
    viewer_email = f"viewer2-{uid}@example.com"
    u = User(id=uid, display_name="Viewer2", email=viewer_email, role="member",
             password_hash=hash_password("viewerpass2"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(
        project_id=minimal_project_ids["project_id"],
        user_id=uid,
        role=ProjectMemberRole.VIEWER.value,
    ))
    db_session.commit()

    _override_provider(client, mock_provider)
    lr = client.post("/api/v1/auth/login", json={"email": viewer_email, "password": "viewerpass2"})
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    pid = _pid(minimal_project_ids)
    r = client.post(f"/api/v1/projects/{pid}/git/create-branch",
                    json={"branch_name": "trident/aaaaaaaa/test"}, headers=vh)
    assert r.status_code == 403
    _clear_provider(client)


# ── create-repo ───────────────────────────────────────────────────────────────

def test_create_repo_persists_git_repo_link(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    r = git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["owner"] == "acme"
    assert body["provider"] == "github"
    assert "token" not in r.text.lower()

    db_session.expire_all()
    link = db_session.scalars(
        select(GitRepoLink).where(GitRepoLink.project_id == minimal_project_ids["project_id"])
    ).first()
    assert link is not None
    assert link.owner == "acme"
    assert link.clone_url.startswith("https://")


def test_create_repo_updates_project_git_fields(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
    db_session.expire_all()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    assert proj.git_remote_url == FAKE_REPO.clone_url
    assert proj.git_branch == "main"


def test_create_repo_with_scaffold_calls_push_files(git_client, minimal_project_ids, mock_provider) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    r = git_client.post(
        f"/api/v1/projects/{pid}/git/create-repo",
        json={"private": True, "init_scaffold": True},
        headers=h,
    )
    assert r.status_code == 201, r.text
    mock_provider.push_files.assert_called_once()
    call_kwargs = mock_provider.push_files.call_args.kwargs
    assert "README.md" in call_kwargs["files"]
    assert ".gitignore" in call_kwargs["files"]


def test_create_repo_emits_audit(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.GIT_REPO_CREATED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert p["owner"] == "acme"
    assert "token" not in json.dumps(p)


def test_create_repo_409_on_duplicate(git_client, minimal_project_ids) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
    r2 = git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
    assert r2.status_code == 409
    assert "repo_already_linked" in r2.json()["detail"]


# ── link-repo ─────────────────────────────────────────────────────────────────

def test_link_repo_persists_repo_link(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    r = git_client.post(
        f"/api/v1/projects/{pid}/git/link-repo",
        json={"clone_url": "https://github.com/acme/my-project.git"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["provider"] == "github"
    assert body["clone_url"].startswith("https://")
    assert "token" not in r.text.lower()

    db_session.expire_all()
    link = db_session.scalars(
        select(GitRepoLink).where(GitRepoLink.project_id == minimal_project_ids["project_id"])
    ).first()
    assert link is not None


def test_link_repo_409_on_duplicate(git_client, minimal_project_ids) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/link-repo",
                    json={"clone_url": "https://github.com/acme/my-project.git"}, headers=h)
    r2 = git_client.post(f"/api/v1/projects/{pid}/git/link-repo",
                         json={"clone_url": "https://github.com/acme/my-project.git"}, headers=h)
    assert r2.status_code == 409


def test_link_repo_emits_audit(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(
        f"/api/v1/projects/{pid}/git/link-repo",
        json={"clone_url": "https://github.com/acme/my-project.git"},
        headers=h,
    )
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.GIT_REPO_LINKED.value)
    ).first()
    assert row is not None
    assert "token" not in json.dumps(row.event_payload_json)


def test_link_repo_provider_error_mapped(client, minimal_project_ids, mock_provider) -> None:
    mock_provider.link_repo.side_effect = GitProviderError(
        "bad URL", reason_code="invalid_clone_url"
    )
    _override_provider(client, mock_provider)
    h = _headers(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/git/link-repo",
        json={"clone_url": "https://github.com/acme/my-project.git"},
        headers=h,
    )
    assert r.status_code == 502
    assert "git_provider_error" in r.json()["detail"]
    _clear_provider(client)


# ── repo-status ───────────────────────────────────────────────────────────────

def test_repo_status_404_when_not_linked(git_client, minimal_project_ids) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    r = git_client.get(f"/api/v1/projects/{pid}/git/repo-status", headers=h)
    assert r.status_code == 404
    assert "repo_not_linked" in r.json()["detail"]


def test_repo_status_returns_sanitized_data(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
    r = git_client.get(f"/api/v1/projects/{pid}/git/repo-status", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "clone_url" in body
    assert "token" not in r.text.lower()
    assert "password" not in r.text.lower()
    assert body["clone_url"].startswith("https://")


# ── create-branch ─────────────────────────────────────────────────────────────

def test_create_branch_404_when_no_repo(git_client, minimal_project_ids) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    r = git_client.post(f"/api/v1/projects/{pid}/git/create-branch",
                        json={"branch_name": "trident/aaaaaaaa/test"}, headers=h)
    assert r.status_code == 404


def test_create_branch_persists_branch_log(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)

    db_session.expire_all()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    if proj:
        proj.git_commit_sha = SHA_MAIN

    r = git_client.post(f"/api/v1/projects/{pid}/git/create-branch",
                        json={"branch_name": "trident/aaaaaaaa/my-feature"}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["branch_name"] == "trident/aaaaaaaa/my-feature"  # response uses the requested name

    db_session.expire_all()
    log_row = db_session.scalars(
        select(GitBranchLog).where(GitBranchLog.project_id == minimal_project_ids["project_id"])
    ).first()
    assert log_row is not None
    assert log_row.event_type == "branch_created"


def test_create_branch_with_directive_id(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)

    body_req = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Add feature",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body_req)
    db_session.commit()

    r = git_client.post(
        f"/api/v1/projects/{pid}/git/create-branch",
        json={"directive_id": str(d.id)},
        headers=h,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["directive_id"] == str(d.id)

    db_session.expire_all()
    log_row = db_session.scalars(
        select(GitBranchLog).where(
            GitBranchLog.project_id == minimal_project_ids["project_id"],
            GitBranchLog.directive_id == d.id,
        )
    ).first()
    assert log_row is not None


def test_create_branch_directive_mismatch_rejected(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
    r = git_client.post(
        f"/api/v1/projects/{pid}/git/create-branch",
        json={"directive_id": str(uuid.uuid4())},  # random non-existent directive
        headers=h,
    )
    assert r.status_code == 422
    assert "directive_not_in_project" in r.json()["detail"]


def test_create_branch_emits_audit(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
    git_client.post(f"/api/v1/projects/{pid}/git/create-branch",
                    json={"branch_name": "trident/aaaaaaaa/feat"}, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.GIT_BRANCH_CREATED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert "branch_name" in p
    assert "token" not in json.dumps(p)


# ── branches list ─────────────────────────────────────────────────────────────

def test_branches_list_returns_log_entries(git_client, minimal_project_ids, db_session) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h)
    git_client.post(f"/api/v1/projects/{pid}/git/create-branch",
                    json={"branch_name": "trident/aaaaaaaa/feat1"}, headers=h)
    git_client.post(f"/api/v1/projects/{pid}/git/create-branch",
                    json={"branch_name": "trident/bbbbbbbb/feat2"}, headers=h)

    r = git_client.get(f"/api/v1/projects/{pid}/git/branches", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 2
    assert all("branch_name" in i for i in items)
    assert all("token" not in json.dumps(i) for i in items)


def test_branches_empty_before_any_branch(git_client, minimal_project_ids) -> None:
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    r = git_client.get(f"/api/v1/projects/{pid}/git/branches", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []


# ── No token in any response ──────────────────────────────────────────────────

def test_no_token_in_any_git_api_response(git_client, minimal_project_ids) -> None:
    """Shotgun check: none of the git endpoints return token-like strings."""
    token_markers = ["Bearer ", "github_pat_", "ghp_", "Authorization:"]
    h = _headers(git_client, minimal_project_ids)
    pid = _pid(minimal_project_ids)

    responses = [
        git_client.post(f"/api/v1/projects/{pid}/git/create-repo", json={"private": True}, headers=h),
        git_client.get(f"/api/v1/projects/{pid}/git/repo-status", headers=h),
        git_client.get(f"/api/v1/projects/{pid}/git/branches", headers=h),
    ]
    for resp in responses:
        text = resp.text
        for marker in token_markers:
            assert marker not in text, f"Token marker '{marker}' found in response: {text[:200]}"
