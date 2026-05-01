"""TRIDENT_IMPLEMENTATION_DIRECTIVE_ONBOARD_001 — schema acceptance tests."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.models.enums import AuditEventType
from app.models.project import Project
from app.models.project_onboarding import ProjectOnboarding
from app.models.state_enums import GateStatus, OnboardingStatus, ProjectGateType


# ── Enum correctness ──────────────────────────────────────────────────────────

def test_onboarding_status_values() -> None:
    expected = {
        "PENDING", "SCANNING", "SCANNED", "INDEXING",
        "INDEXED", "AWAITING_APPROVAL", "APPROVED", "REJECTED",
    }
    assert set(OnboardingStatus) == expected


def test_project_gate_type_includes_onboarding_audit() -> None:
    assert ProjectGateType.ONBOARDING_AUDIT == "ONBOARDING_AUDIT"
    assert "ONBOARDING_AUDIT" in {g.value for g in ProjectGateType}


def test_audit_event_type_onboarding_events() -> None:
    required = {
        "ONBOARDING_STARTED",
        "ONBOARDING_SCAN_COMPLETE",
        "ONBOARDING_INDEX_QUEUED",
        "ONBOARDING_APPROVED",
        "ONBOARDING_REJECTED",
    }
    values = {e.value for e in AuditEventType}
    missing = required - values
    assert not missing, f"Missing audit event types: {missing}"


# ── SQLite schema introspection ───────────────────────────────────────────────

def test_project_onboarding_table_exists(sqlite_engine) -> None:
    insp = inspect(sqlite_engine)
    tables = set(insp.get_table_names())
    assert "project_onboarding" in tables, "project_onboarding table not created"


def test_project_onboarding_all_columns_present(sqlite_engine) -> None:
    insp = inspect(sqlite_engine)
    cols = {c["name"] for c in insp.get_columns("project_onboarding")}
    required = {
        "id", "project_id", "status",
        "repo_local_path", "git_remote_url", "git_branch", "git_commit_sha",
        "language_primary", "languages_detected", "framework_hints",
        "scan_artifact_json", "asbuilt_artifact_json",
        "index_job_id",
        "approved_by_user_id", "approved_at", "rejection_reason",
        "previous_onboarding_id",
        "created_at", "updated_at",
    }
    missing = required - cols
    assert not missing, f"Missing columns: {missing}"


def test_projects_onboarding_columns_present(sqlite_engine) -> None:
    insp = inspect(sqlite_engine)
    cols = {c["name"] for c in insp.get_columns("projects")}
    required = {
        "onboarding_status", "git_branch", "git_commit_sha",
        "language_primary", "description",
    }
    missing = required - cols
    assert not missing, f"Missing project columns: {missing}"


# ── ORM CRUD ──────────────────────────────────────────────────────────────────

def test_create_onboarding_row(db_session: Session, minimal_project_ids: dict) -> None:
    row = ProjectOnboarding(
        project_id=minimal_project_ids["project_id"],
        status=OnboardingStatus.PENDING.value,
        repo_local_path="/home/dev/myrepo",
        git_remote_url="https://github.com/acme/myrepo.git",
        git_branch="main",
        git_commit_sha="abc123def456abc123def456abc123def456abc1",
        language_primary="python",
        languages_detected={"python": 0.78, "typescript": 0.12},
        framework_hints=["fastapi", "react", "docker"],
        scan_artifact_json={"schema": "onboarding_scan_v1", "checks": {}},
    )
    db_session.add(row)
    db_session.flush()
    assert row.id is not None
    db_session.commit()

    fetched = db_session.get(ProjectOnboarding, row.id)
    assert fetched is not None
    assert fetched.status == OnboardingStatus.PENDING.value
    assert fetched.language_primary == "python"
    assert fetched.languages_detected["typescript"] == 0.12
    assert fetched.framework_hints == ["fastapi", "react", "docker"]
    assert fetched.scan_artifact_json["schema"] == "onboarding_scan_v1"


def test_project_onboarding_previous_chain(db_session: Session, minimal_project_ids: dict) -> None:
    first = ProjectOnboarding(
        project_id=minimal_project_ids["project_id"],
        status=OnboardingStatus.APPROVED.value,
        git_commit_sha="sha001",
    )
    db_session.add(first)
    db_session.flush()

    second = ProjectOnboarding(
        project_id=minimal_project_ids["project_id"],
        status=OnboardingStatus.PENDING.value,
        git_commit_sha="sha002",
        previous_onboarding_id=first.id,
    )
    db_session.add(second)
    db_session.flush()
    db_session.commit()

    fetched = db_session.get(ProjectOnboarding, second.id)
    assert fetched is not None
    assert fetched.previous_onboarding_id == first.id


def test_project_onboarding_nullable_fields_defaults(db_session: Session, minimal_project_ids: dict) -> None:
    row = ProjectOnboarding(
        project_id=minimal_project_ids["project_id"],
        status=OnboardingStatus.PENDING.value,
    )
    db_session.add(row)
    db_session.flush()
    db_session.commit()

    fetched = db_session.get(ProjectOnboarding, row.id)
    assert fetched is not None
    assert fetched.repo_local_path is None
    assert fetched.approved_at is None
    assert fetched.scan_artifact_json is None
    assert fetched.previous_onboarding_id is None


def test_project_onboarding_fields_on_project(db_session: Session, minimal_project_ids: dict) -> None:
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    # All new nullable fields should exist and default to None for existing rows
    assert hasattr(proj, "onboarding_status")
    assert hasattr(proj, "git_branch")
    assert hasattr(proj, "git_commit_sha")
    assert hasattr(proj, "language_primary")
    assert hasattr(proj, "description")
    assert proj.onboarding_status is None
    assert proj.description is None

    proj.onboarding_status = OnboardingStatus.PENDING.value
    proj.git_branch = "main"
    proj.git_commit_sha = "abc123"
    proj.language_primary = "python"
    proj.description = "My existing project"
    db_session.flush()
    db_session.commit()

    db_session.expire(proj)
    refetched = db_session.get(Project, proj.id)
    assert refetched is not None
    assert refetched.onboarding_status == OnboardingStatus.PENDING.value
    assert refetched.git_commit_sha == "abc123"
    assert refetched.description == "My existing project"


def test_project_onboarding_approval_fields(db_session: Session, minimal_project_ids: dict) -> None:
    from datetime import datetime, timezone

    user_id = minimal_project_ids["user_id"]
    row = ProjectOnboarding(
        project_id=minimal_project_ids["project_id"],
        status=OnboardingStatus.AWAITING_APPROVAL.value,
        git_commit_sha="sha_approve_test",
    )
    db_session.add(row)
    db_session.flush()

    now = datetime.now(timezone.utc)
    row.status = OnboardingStatus.APPROVED.value
    row.approved_by_user_id = user_id
    row.approved_at = now
    db_session.flush()
    db_session.commit()

    fetched = db_session.get(ProjectOnboarding, row.id)
    assert fetched is not None
    assert fetched.status == OnboardingStatus.APPROVED.value
    assert fetched.approved_by_user_id == user_id
    assert fetched.approved_at is not None


def test_project_onboarding_rejection(db_session: Session, minimal_project_ids: dict) -> None:
    row = ProjectOnboarding(
        project_id=minimal_project_ids["project_id"],
        status=OnboardingStatus.AWAITING_APPROVAL.value,
    )
    db_session.add(row)
    db_session.flush()

    row.status = OnboardingStatus.REJECTED.value
    row.rejection_reason = "Secrets found in scan"
    db_session.flush()
    db_session.commit()

    fetched = db_session.get(ProjectOnboarding, row.id)
    assert fetched is not None
    assert fetched.status == OnboardingStatus.REJECTED.value
    assert "Secrets" in (fetched.rejection_reason or "")


def test_scan_and_asbuilt_artifacts(db_session: Session, minimal_project_ids: dict) -> None:
    scan = {
        "schema": "onboarding_scan_v1",
        "git_commit_sha": "deadbeef",
        "checks": {
            "secrets_scan": {"status": "PASS", "findings_count": 0},
            "docker_readiness": {"status": "PASS", "has_dockerfile": True},
        },
    }
    asbuilt = {
        "schema": "asbuilt_architecture_v1",
        "sections": {"system_overview": "A Python FastAPI backend."},
    }
    row = ProjectOnboarding(
        project_id=minimal_project_ids["project_id"],
        status=OnboardingStatus.AWAITING_APPROVAL.value,
        scan_artifact_json=scan,
        asbuilt_artifact_json=asbuilt,
    )
    db_session.add(row)
    db_session.flush()
    db_session.commit()

    fetched = db_session.get(ProjectOnboarding, row.id)
    assert fetched is not None
    assert fetched.scan_artifact_json["checks"]["secrets_scan"]["findings_count"] == 0
    assert fetched.asbuilt_artifact_json["sections"]["system_overview"] == "A Python FastAPI backend."


# ── Regression: existing project + directive tests still pass ─────────────────

def test_existing_project_model_unaffected(db_session: Session, minimal_project_ids: dict) -> None:
    """Existing fields on Project (pre-ONBOARD_001) must continue to work."""
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    assert proj.name is not None
    assert proj.workspace_id is not None
    assert proj.allowed_root_path is not None
    assert proj.created_at is not None


def test_alembic_onboard001001_is_in_revision_chain() -> None:
    """onboard001001 must exist in the migration chain (not necessarily the current head)."""
    from alembic.script import ScriptDirectory
    from alembic.config import Config
    import os

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    scripts = ScriptDirectory.from_config(cfg)
    revisions = {s.revision for s in scripts.walk_revisions()}
    assert "onboard001001" in revisions, f"onboard001001 not found in migration chain"
