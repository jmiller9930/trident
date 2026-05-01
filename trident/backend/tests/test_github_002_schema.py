"""TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_002 — data model acceptance tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.enums import AuditEventType, ProofObjectType
from app.models.git_branch_log import GIT_BRANCH_LOG_EVENTS, GitBranchLog
from app.models.git_repo_link import GitRepoLink


# ── Enum correctness ──────────────────────────────────────────────────────────

def test_proof_object_type_git_values() -> None:
    assert ProofObjectType.GIT_BRANCH_CREATED == "GIT_BRANCH_CREATED"
    assert ProofObjectType.GIT_COMMIT_PUSHED == "GIT_COMMIT_PUSHED"
    vals = {p.value for p in ProofObjectType}
    assert "GIT_BRANCH_CREATED" in vals
    assert "GIT_COMMIT_PUSHED" in vals


def test_audit_event_type_git_values() -> None:
    required = {"GIT_REPO_CREATED", "GIT_REPO_LINKED", "GIT_BRANCH_CREATED", "GIT_COMMIT_PUSHED"}
    present = {e.value for e in AuditEventType}
    missing = required - present
    assert not missing, f"Missing AuditEventType values: {missing}"


def test_git_branch_log_events_constant() -> None:
    assert "branch_created" in GIT_BRANCH_LOG_EVENTS
    assert "commit_pushed" in GIT_BRANCH_LOG_EVENTS


# ── Table existence ───────────────────────────────────────────────────────────

def test_git_repo_links_table_exists(sqlite_engine) -> None:
    insp = inspect(sqlite_engine)
    assert "git_repo_links" in set(insp.get_table_names())


def test_git_branch_log_table_exists(sqlite_engine) -> None:
    insp = inspect(sqlite_engine)
    assert "git_branch_log" in set(insp.get_table_names())


# ── Column presence ───────────────────────────────────────────────────────────

def test_git_repo_links_columns(sqlite_engine) -> None:
    insp = inspect(sqlite_engine)
    cols = {c["name"] for c in insp.get_columns("git_repo_links")}
    required = {
        "id", "project_id", "provider", "owner", "repo_name",
        "clone_url", "html_url", "default_branch", "private",
        "linked_by_user_id", "linked_at", "created_at", "updated_at",
    }
    assert required <= cols


def test_git_branch_log_columns(sqlite_engine) -> None:
    insp = inspect(sqlite_engine)
    cols = {c["name"] for c in insp.get_columns("git_branch_log")}
    required = {
        "id", "project_id", "directive_id", "provider", "branch_name",
        "commit_sha", "commit_message", "created_by_user_id", "event_type", "created_at",
    }
    assert required <= cols


def test_git_repo_links_has_no_token_fields(sqlite_engine) -> None:
    insp = inspect(sqlite_engine)
    cols = {c["name"] for c in insp.get_columns("git_repo_links")}
    forbidden = {"token", "credential", "password", "secret", "api_key", "github_token"}
    overlap = forbidden & cols
    assert not overlap, f"Credential fields must not exist in git_repo_links: {overlap}"


def test_git_branch_log_has_no_token_fields(sqlite_engine) -> None:
    insp = inspect(sqlite_engine)
    cols = {c["name"] for c in insp.get_columns("git_branch_log")}
    forbidden = {"token", "credential", "password", "secret", "api_key", "github_token"}
    overlap = forbidden & cols
    assert not overlap, f"Credential fields must not exist in git_branch_log: {overlap}"


# ── ORM CRUD ──────────────────────────────────────────────────────────────────

def test_create_git_repo_link(db_session: Session, minimal_project_ids: dict) -> None:
    row = GitRepoLink(
        project_id=minimal_project_ids["project_id"],
        provider="github",
        owner="acme-corp",
        repo_name="trident-backend",
        clone_url="https://github.com/acme-corp/trident-backend.git",
        html_url="https://github.com/acme-corp/trident-backend",
        default_branch="main",
        private=True,
        linked_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(row)
    db_session.flush()
    db_session.commit()

    fetched = db_session.get(GitRepoLink, row.id)
    assert fetched is not None
    assert fetched.owner == "acme-corp"
    assert fetched.repo_name == "trident-backend"
    assert fetched.provider == "github"
    assert fetched.private is True
    assert "acme-corp" in fetched.clone_url
    assert fetched.linked_by_user_id == minimal_project_ids["user_id"]


def test_git_repo_link_unique_per_project(db_session: Session, minimal_project_ids: dict) -> None:
    """Only one repo link allowed per project (unique constraint on project_id)."""
    from sqlalchemy.exc import IntegrityError

    first = GitRepoLink(
        project_id=minimal_project_ids["project_id"],
        provider="github",
        owner="acme",
        repo_name="repo1",
        clone_url="https://github.com/acme/repo1.git",
        html_url="https://github.com/acme/repo1",
        default_branch="main",
        private=False,
        linked_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(first)
    db_session.flush()

    duplicate = GitRepoLink(
        project_id=minimal_project_ids["project_id"],
        provider="github",
        owner="acme",
        repo_name="repo2",
        clone_url="https://github.com/acme/repo2.git",
        html_url="https://github.com/acme/repo2",
        default_branch="main",
        private=False,
        linked_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_create_git_branch_log_with_directive(db_session: Session, minimal_project_ids: dict) -> None:
    from app.repositories.directive_repository import DirectiveRepository
    from app.schemas.directive import CreateDirectiveRequest

    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="Wire GitHub branch",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()

    row = GitBranchLog(
        project_id=minimal_project_ids["project_id"],
        directive_id=d.id,
        provider="github",
        branch_name="trident/d3f1a2b4/wire-github-branch",
        commit_sha="abc123def456abc123def456abc123def456abc1",
        commit_message="Scaffold for GITHUB_002",
        created_by_user_id=minimal_project_ids["user_id"],
        event_type="branch_created",
    )
    db_session.add(row)
    db_session.flush()
    db_session.commit()

    fetched = db_session.get(GitBranchLog, row.id)
    assert fetched is not None
    assert fetched.directive_id == d.id
    assert fetched.branch_name == "trident/d3f1a2b4/wire-github-branch"
    assert fetched.event_type == "branch_created"
    assert fetched.commit_sha is not None


def test_create_git_branch_log_without_directive(db_session: Session, minimal_project_ids: dict) -> None:
    row = GitBranchLog(
        project_id=minimal_project_ids["project_id"],
        directive_id=None,
        provider="github",
        branch_name="main",
        commit_sha="scaffold0000000000000000000000000000000000",
        commit_message="Initial scaffold commit",
        created_by_user_id=minimal_project_ids["user_id"],
        event_type="commit_pushed",
    )
    db_session.add(row)
    db_session.flush()
    db_session.commit()

    fetched = db_session.get(GitBranchLog, row.id)
    assert fetched is not None
    assert fetched.directive_id is None
    assert fetched.event_type == "commit_pushed"


def test_multiple_branch_log_entries_same_project(db_session: Session, minimal_project_ids: dict) -> None:
    pid = minimal_project_ids["project_id"]
    uid = minimal_project_ids["user_id"]
    events = [
        ("branch_created", "trident/aaaa0001/feat-a", "sha1"),
        ("commit_pushed",  "trident/aaaa0001/feat-a", "sha2"),
        ("branch_created", "trident/bbbb0002/feat-b", "sha3"),
    ]
    for et, bn, sha in events:
        db_session.add(GitBranchLog(
            project_id=pid, directive_id=None, provider="github",
            branch_name=bn, commit_sha=sha, commit_message="test",
            created_by_user_id=uid, event_type=et,
        ))
    db_session.flush()
    db_session.commit()

    rows = list(db_session.scalars(select(GitBranchLog).where(GitBranchLog.project_id == pid)).all())
    assert len(rows) == 3


def test_git_repo_link_clone_url_https_only(db_session: Session, minimal_project_ids: dict) -> None:
    """Verify HTTPS clone URL is stored correctly (no SSH, no tokenized URLs)."""
    row = GitRepoLink(
        project_id=minimal_project_ids["project_id"],
        provider="github",
        owner="org",
        repo_name="safe-repo",
        clone_url="https://github.com/org/safe-repo.git",
        html_url="https://github.com/org/safe-repo",
        default_branch="main",
        private=True,
        linked_by_user_id=minimal_project_ids["user_id"],
    )
    db_session.add(row)
    db_session.flush()
    db_session.commit()

    fetched = db_session.get(GitRepoLink, row.id)
    assert fetched is not None
    assert fetched.clone_url.startswith("https://")
    assert "@" not in fetched.clone_url  # no tokenized https://token@github.com URLs


# ── Alembic head check ────────────────────────────────────────────────────────

def test_alembic_github002001_in_chain() -> None:
    import os
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    scripts = ScriptDirectory.from_config(cfg)
    revisions = {s.revision for s in scripts.walk_revisions()}
    assert "github002001" in revisions, "github002001 not found in migration chain"
