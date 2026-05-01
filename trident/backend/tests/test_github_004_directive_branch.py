"""TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_004 — directive issue → git branch binding."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.api.deps.git_deps import get_git_provider, get_optional_git_provider
from app.git_provider.base import (
    BranchInfo,
    GitProvider,
    GitProviderDisabledError,
    GitProviderError,
    RepoInfo,
)
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.git_branch_log import GitBranchLog
from app.git_provider.branch_naming import directive_branch_name
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.models.enums import DirectiveStatus


# ── Helpers ──────────────────────────────────────────────────────────────────

SHA = "abc123def456abc123def456abc123def456abc1"

FAKE_REPO = RepoInfo(
    provider="github",
    owner="acme",
    repo_name="my-project",
    clone_url="https://github.com/acme/my-project.git",
    html_url="https://github.com/acme/my-project",
    default_branch="main",
    private=True,
    created=False,
)


def _mock_provider(branch_sha: str = SHA) -> MagicMock:
    m = MagicMock(spec=GitProvider)
    m.provider_name = "github"
    m.create_branch.return_value = BranchInfo(
        provider="github",
        branch_name="trident/aaaaaaaa/feat",
        commit_sha=branch_sha,
    )
    m.get_default_branch_sha.return_value = branch_sha
    m.link_repo.return_value = FAKE_REPO
    m.get_repo_info.return_value = FAKE_REPO
    return m


def _login(client, ids):
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _create_draft(db_session, ids) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Add feature Z",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


def _link_repo(client, ids, h, provider):
    pid = str(ids["project_id"])
    client.app.dependency_overrides[get_git_provider] = lambda: provider
    r = client.post(f"/api/v1/projects/{pid}/git/link-repo",
                    json={"clone_url": "https://github.com/acme/my-project.git"}, headers=h)
    assert r.status_code == 201, r.text
    client.app.dependency_overrides.pop(get_git_provider, None)


def _override_optional_provider(client, provider):
    client.app.dependency_overrides[get_optional_git_provider] = lambda: provider


def _clear_optional_provider(client):
    client.app.dependency_overrides.pop(get_optional_git_provider, None)


# ── Issue without repo linked ─────────────────────────────────────────────────

def test_issue_without_repo_linked_succeeds(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_draft(db_session, minimal_project_ids)
    r = client.post(f"/api/v1/directives/{did}/issue", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == DirectiveStatus.ISSUED.value
    assert body["git_branch_created"] is False
    assert body["git_branch_name"] is None
    assert body["git_warning"] is None


# ── Issue with repo linked + mocked provider ──────────────────────────────────

def test_issue_with_linked_repo_creates_branch(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    _link_repo(client, minimal_project_ids, h, provider)

    did = _create_draft(db_session, minimal_project_ids)
    _override_optional_provider(client, provider)
    try:
        r = client.post(f"/api/v1/directives/{did}/issue", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == DirectiveStatus.ISSUED.value
        assert body["git_branch_created"] is True
        assert body["git_branch_name"] is not None
        assert body["git_commit_sha"] == SHA
        assert body["git_warning"] is None
        from app.git_provider.branch_naming import validate_trident_branch_name
        assert validate_trident_branch_name(body["git_branch_name"])
    finally:
        _clear_optional_provider(client)


def test_issue_branch_name_follows_standard(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    _link_repo(client, minimal_project_ids, h, provider)

    did = _create_draft(db_session, minimal_project_ids)
    _override_optional_provider(client, provider)
    try:
        r = client.post(f"/api/v1/directives/{did}/issue", headers=h)
        branch = r.json()["git_branch_name"]
        short_id = str(did).replace("-", "")[:8]
        assert branch.startswith(f"trident/{short_id}/")
    finally:
        _clear_optional_provider(client)


def test_issue_branch_log_row_persisted(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    _link_repo(client, minimal_project_ids, h, provider)

    did = _create_draft(db_session, minimal_project_ids)
    _override_optional_provider(client, provider)
    try:
        client.post(f"/api/v1/directives/{did}/issue", headers=h)
        db_session.expire_all()
        log = db_session.scalars(
            select(GitBranchLog).where(GitBranchLog.directive_id == did)
        ).first()
        assert log is not None
        assert log.event_type == "branch_created"
        assert log.commit_sha == SHA
    finally:
        _clear_optional_provider(client)


def test_issue_branch_created_audit_emitted(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    _link_repo(client, minimal_project_ids, h, provider)

    did = _create_draft(db_session, minimal_project_ids)
    _override_optional_provider(client, provider)
    try:
        client.post(f"/api/v1/directives/{did}/issue", headers=h)
        db_session.expire_all()
        row = db_session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == AuditEventType.GIT_BRANCH_CREATED.value)
        ).first()
        assert row is not None
        p = row.event_payload_json
        assert "branch_name" in p
        assert "token" not in json.dumps(p)
    finally:
        _clear_optional_provider(client)


# ── Provider failure is non-blocking ─────────────────────────────────────────

def test_provider_failure_leaves_directive_issued(client, minimal_project_ids, db_session) -> None:
    provider = _mock_provider()
    provider.create_branch.side_effect = GitProviderError("API error", reason_code="github_api_error")
    h = _login(client, minimal_project_ids)
    _link_repo(client, minimal_project_ids, h, _mock_provider())  # link succeeds
    # Re-set side_effect on the mock used for issue
    _override_optional_provider(client, provider)
    did = _create_draft(db_session, minimal_project_ids)
    try:
        r = client.post(f"/api/v1/directives/{did}/issue", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == DirectiveStatus.ISSUED.value
        assert body["git_branch_created"] is False
        assert body["git_warning"] is not None
        assert "git_branch_create_failed" in body["git_warning"]
    finally:
        _clear_optional_provider(client)


def test_provider_failure_emits_failed_audit(client, minimal_project_ids, db_session) -> None:
    link_provider = _mock_provider()
    h = _login(client, minimal_project_ids)
    _link_repo(client, minimal_project_ids, h, link_provider)

    fail_provider = _mock_provider()
    fail_provider.create_branch.side_effect = GitProviderError("fail", reason_code="github_timeout")
    _override_optional_provider(client, fail_provider)
    did = _create_draft(db_session, minimal_project_ids)
    try:
        client.post(f"/api/v1/directives/{did}/issue", headers=h)
        db_session.expire_all()
        row = db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == AuditEventType.GIT_BRANCH_CREATE_FAILED.value
            )
        ).first()
        assert row is not None
        p = row.event_payload_json
        assert p["provider_error_code"] == "github_timeout"
        assert "token" not in json.dumps(p)
    finally:
        _clear_optional_provider(client)


# ── Regression: existing directive tests unaffected ───────────────────────────

def test_existing_issue_response_still_works(client, minimal_project_ids, db_session) -> None:
    """The old DirectiveSummary fields must all be present (backward-compatible)."""
    h = _login(client, minimal_project_ids)
    did = _create_draft(db_session, minimal_project_ids)
    r = client.post(f"/api/v1/directives/{did}/issue", headers=h)
    assert r.status_code == 200
    body = r.json()
    for field in ("id", "status", "title", "project_id", "workspace_id",
                  "created_by_user_id", "created_at", "updated_at"):
        assert field in body, f"Missing backward-compatible field: {field}"


def test_duplicate_issue_still_409(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_draft(db_session, minimal_project_ids)
    client.post(f"/api/v1/directives/{did}/issue", headers=h)
    r2 = client.post(f"/api/v1/directives/{did}/issue", headers=h)
    assert r2.status_code == 409


def test_no_token_in_issue_response(client, minimal_project_ids, db_session) -> None:
    h = _login(client, minimal_project_ids)
    did = _create_draft(db_session, minimal_project_ids)
    r = client.post(f"/api/v1/directives/{did}/issue", headers=h)
    text = r.text
    for marker in ("github_pat_", "ghp_", "Bearer github", "Authorization: Bearer gh"):
        assert marker not in text
