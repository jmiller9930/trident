"""TRIDENT_IMPLEMENTATION_DIRECTIVE_ONBOARD_002 — onboarding scan service + endpoints."""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.project_onboarding import ProjectOnboarding
from app.models.state_enums import OnboardingStatus
from app.services.onboarding_scan_service import (
    SCAN_SCHEMA,
    OnboardingScanService,
    PathTraversalError,
    _resolve_safe,
)

REQUIRED_CHECK_KEYS = {
    "git_clean", "structure", "languages", "frameworks", "dependencies",
    "docker_readiness", "env_files", "secrets_scan", "tests", "docs", "gitignore",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_repo(tmp_path: Path, *, files: dict[str, str] | None = None) -> Path:
    """Create a minimal fake repo with optional extra files."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "requirements.txt").write_text("fastapi>=0.109\npydantic>=2.0\n")
    (root / "README.md").write_text("# My project\n")
    (root / ".gitignore").write_text(".env\n*.pem\n*.key\n")
    (root / "Dockerfile").write_text("FROM python:3.11\n")
    src = root / "src"
    src.mkdir()
    (src / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("def test_ok(): assert True\n")
    if files:
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
    return root


# ── OnboardingScanService unit tests ─────────────────────────────────────────

def test_scan_returns_all_required_check_keys(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run(git_commit_sha="abc123")
    assert result["schema"] == SCAN_SCHEMA
    assert result["source"] == "live"
    assert set(result["checks"].keys()) == REQUIRED_CHECK_KEYS


def test_scan_git_clean_pass_with_sha(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run(git_commit_sha="deadbeef")
    assert result["checks"]["git_clean"]["status"] == "PASS"
    assert "deadbeef" in result["checks"]["git_clean"]["detail"]


def test_scan_git_clean_warn_without_sha(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run()
    assert result["checks"]["git_clean"]["status"] == "WARN"


def test_scan_detects_python_language(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run()
    langs = result["checks"]["languages"]
    assert langs["primary"] == "python"
    assert "python" in langs["breakdown"]


def test_scan_detects_frameworks(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run()
    hints = result["checks"]["frameworks"]["hints"]
    assert "python-pip" in hints
    assert "docker" in hints


def test_scan_detects_dependency_files(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run()
    deps = result["checks"]["dependencies"]
    assert deps["count"] >= 1
    assert any("requirements.txt" in f for f in deps["files"])


def test_scan_detects_dockerfile(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run()
    docker = result["checks"]["docker_readiness"]
    assert docker["status"] == "PASS"
    assert docker["has_dockerfile"] is True


def test_scan_detects_test_dirs(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run()
    tests = result["checks"]["tests"]
    assert tests["status"] == "PASS"
    assert any("test" in d for d in tests["test_dirs"])


def test_scan_detects_readme(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run()
    docs = result["checks"]["docs"]
    assert docs["has_readme"] is True


def test_scan_detects_gitignore(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run()
    gi = result["checks"]["gitignore"]
    assert gi["status"] == "PASS"
    assert gi["present"] is True
    assert gi["ignores_env"] is True


def test_scan_no_secrets_in_clean_repo(tmp_path: Path) -> None:
    root = _make_repo(tmp_path)
    result = OnboardingScanService(str(root)).run()
    sec = result["checks"]["secrets_scan"]
    assert sec["status"] == "PASS"
    assert sec["findings_count"] == 0


def test_scan_counts_secrets_not_values(tmp_path: Path) -> None:
    secret = "SUPER_SECRET_VALUE_DO_NOT_LOG"
    root = _make_repo(tmp_path, files={"config.py": f'api_key = "{secret}"\npassword = "hunter2"\n'})
    result = OnboardingScanService(str(root)).run()
    sec = result["checks"]["secrets_scan"]
    assert sec["findings_count"] >= 2
    # The actual secret VALUE must not appear in the artifact JSON
    serialized = json.dumps(result)
    assert secret not in serialized
    assert "hunter2" not in serialized
    # Gate must be BLOCKING
    assert result["gate_recommendation"] == "BLOCKING"


def test_scan_env_file_warns_if_raw_env(tmp_path: Path) -> None:
    root = _make_repo(tmp_path, files={".env": "DB_PASSWORD=oops\n"})
    result = OnboardingScanService(str(root)).run()
    env = result["checks"]["env_files"]
    assert env["has_raw_env"] is True
    assert env["status"] == "WARN"


def test_scan_unavailable_source_for_missing_path() -> None:
    svc = OnboardingScanService("/nonexistent/path/abc123xyz")
    result = svc.run()
    assert result["source"] == "unavailable"
    assert result["gate_recommendation"] == "MISSING"
    assert result["checks"] == {}


def test_scan_uses_client_manifest_when_path_inaccessible() -> None:
    manifest = {
        "checks": {"git_clean": {"status": "PASS"}},
        "gate_recommendation": "READY",
        "summary_text": "Provided by extension.",
    }
    svc = OnboardingScanService("/no/such/path", client_manifest=manifest)
    result = svc.run(git_commit_sha="sha_from_client")
    assert result["source"] == "client_manifest"
    assert result["git_commit_sha"] == "sha_from_client"
    assert result["gate_recommendation"] == "READY"


def test_resolve_safe_blocks_traversal(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    escaping = root / ".." / "outside.txt"
    with pytest.raises(PathTraversalError):
        _resolve_safe(escaping, root)


def test_resolve_safe_allows_file_inside_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    inside = root / "src" / "main.py"
    resolved = _resolve_safe(inside, root)
    assert str(resolved).startswith(str(root.resolve()))


# ── API endpoint tests ────────────────────────────────────────────────────────

def _login_headers(client, minimal_project_ids):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": minimal_project_ids["email"], "password": minimal_project_ids["password"]},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def test_begin_creates_onboarding_row(client, minimal_project_ids, db_session) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    r = client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={
            "repo_local_path": "/home/dev/myrepo",
            "git_remote_url": "https://github.com/acme/myrepo.git",
            "git_branch": "main",
            "git_commit_sha": "sha001",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == OnboardingStatus.PENDING.value
    assert body["git_commit_sha"] == "sha001"
    assert uuid.UUID(body["onboarding_id"])

    import uuid as _uuid
    oid = _uuid.UUID(body["onboarding_id"])
    row = db_session.get(ProjectOnboarding, oid)
    assert row is not None
    assert row.status == OnboardingStatus.PENDING.value


import uuid


def test_begin_emits_onboarding_started_audit(client, minimal_project_ids, db_session) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": "/repo", "git_commit_sha": "sha_audit"},
        headers=h,
    )
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.ONBOARDING_STARTED.value)
    ).first()
    assert row is not None
    assert row.event_payload_json["git_commit_sha"] == "sha_audit"


def test_begin_rejects_duplicate_active_onboarding(client, minimal_project_ids) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": "/repo1", "git_commit_sha": "s1"},
        headers=h,
    )
    r2 = client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": "/repo2", "git_commit_sha": "s2"},
        headers=h,
    )
    assert r2.status_code == 409
    assert "onboarding_already_active" in r2.json()["detail"]


def test_scan_transitions_pending_to_scanned(client, minimal_project_ids, tmp_path) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    root = _make_repo(tmp_path)
    client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": str(root), "git_commit_sha": "sha_scan"},
        headers=h,
    )
    r = client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == OnboardingStatus.SCANNED.value
    artifact = body["scan_artifact_json"]
    assert artifact["schema"] == SCAN_SCHEMA
    assert set(artifact["checks"].keys()) == REQUIRED_CHECK_KEYS


def test_scan_result_has_all_check_keys(client, minimal_project_ids, tmp_path) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    root = _make_repo(tmp_path)
    client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": str(root), "git_commit_sha": "sha_keys"},
        headers=h,
    )
    client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    r = client.get(f"/api/v1/projects/{pid}/onboarding/scan-result", headers=h)
    assert r.status_code == 200, r.text
    artifact = r.json()["scan_artifact_json"]
    assert set(artifact["checks"].keys()) == REQUIRED_CHECK_KEYS


def test_scan_secrets_count_only_not_values(client, minimal_project_ids, tmp_path) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    secret_val = "MY_SECRET_VALUE_DO_NOT_STORE"
    root = _make_repo(tmp_path, files={"conf.py": f'api_key = "{secret_val}"\n'})
    client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": str(root), "git_commit_sha": "sha_sec"},
        headers=h,
    )
    r = client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    assert r.status_code == 200, r.text
    body_text = r.text
    assert secret_val not in body_text
    sec = r.json()["scan_artifact_json"]["checks"]["secrets_scan"]
    assert sec["findings_count"] >= 1


def test_get_status_returns_full_record(client, minimal_project_ids, tmp_path) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    root = _make_repo(tmp_path)
    client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": str(root), "git_commit_sha": "sha_status"},
        headers=h,
    )
    r = client.get(f"/api/v1/projects/{pid}/onboarding/status", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "status" in body
    assert "onboarding_id" in body
    assert "git_commit_sha" in body
    assert body["git_commit_sha"] == "sha_status"


def test_scan_emits_scan_complete_audit(client, minimal_project_ids, db_session, tmp_path) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    root = _make_repo(tmp_path)
    client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": str(root), "git_commit_sha": "sha_audit2"},
        headers=h,
    )
    client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.ONBOARDING_SCAN_COMPLETE.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert p["git_commit_sha"] == "sha_audit2"
    assert "secrets_findings_count" in p
    assert "gate_recommendation" in p


def test_scan_path_unavailable_returns_unavailable_source(client, minimal_project_ids) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": "/nonexistent/path/xyz123", "git_commit_sha": "sha_na"},
        headers=h,
    )
    r = client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    assert r.status_code == 200, r.text
    artifact = r.json()["scan_artifact_json"]
    assert artifact["source"] == "unavailable"
    assert artifact["gate_recommendation"] == "MISSING"


def test_begin_requires_auth(client, minimal_project_ids) -> None:
    pid = str(minimal_project_ids["project_id"])
    r = client.post(
        f"/api/v1/projects/{pid}/onboarding/begin",
        json={"repo_local_path": "/repo"},
    )
    assert r.status_code == 401


def test_scan_requires_existing_onboarding(client, minimal_project_ids) -> None:
    pid = str(minimal_project_ids["project_id"])
    h = _login_headers(client, minimal_project_ids)
    r = client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    assert r.status_code == 404
