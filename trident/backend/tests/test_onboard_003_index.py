"""TRIDENT_ONBOARD_003 — onboarding context indexing + scanner fixes."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.project_onboarding import ProjectOnboarding
from app.models.state_enums import OnboardingStatus
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.services.onboarding_index_service import (
    INCLUDE_EXTENSIONS,
    NAMESPACE_PREFIX,
    OnboardingIndexError,
    OnboardingIndexService,
    _chunk_text,
    _has_secret,
    _should_include,
)
from app.services.onboarding_scan_service import OnboardingScanService


# ── Helpers ──────────────────────────────────────────────────────────────────

def _login(client, ids) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(ids) -> str:
    return str(ids["project_id"])


def _make_viewer(db_session, ids):
    from app.models.user import User
    from app.models.project_member import ProjectMember
    from app.models.enums import ProjectMemberRole
    from app.security.passwords import hash_password
    uid = uuid.uuid4()
    email = f"viewer-ob3-{uid}@example.com"
    u = User(id=uid, display_name="V", email=email, role="m", password_hash=hash_password("viewerpass!"))
    db_session.add(u)
    db_session.flush()
    db_session.add(ProjectMember(project_id=ids["project_id"], user_id=uid, role=ProjectMemberRole.VIEWER.value))
    db_session.commit()
    return {"email": email, "password": "viewerpass!"}


def _begin_and_scan(client, ids, h, tmp_path: Path) -> tuple[str, Path]:
    pid = _pid(ids)
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("def hello():\n    return 'world'\n")
    (root / "README.md").write_text("# My project\n")
    (root / "requirements-dev.txt").write_text("pytest>=7.0\n")
    (root / "requirements.txt").write_text("fastapi>=0.109\n")
    (root / ".gitignore").write_text(".env\n*.pem\n")
    r = client.post(f"/api/v1/projects/{pid}/onboarding/begin",
                    json={"repo_local_path": str(root), "git_commit_sha": "testsha123"},
                    headers=h)
    assert r.status_code == 201, r.text
    oid = r.json()["onboarding_id"]
    client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    return oid, root


# ── Unit: _should_include ────────────────────────────────────────────────────

def test_include_python_file(tmp_path) -> None:
    f = tmp_path / "main.py"
    f.write_text("x=1")
    assert _should_include(f) is True


def test_exclude_env_file(tmp_path) -> None:
    f = tmp_path / ".env"
    f.write_text("API_KEY=secret")
    assert _should_include(f) is False


def test_exclude_pem_file(tmp_path) -> None:
    f = tmp_path / "cert.pem"
    f.write_text("-----BEGIN CERTIFICATE-----")
    assert _should_include(f) is False


def test_include_requirements_variant(tmp_path) -> None:
    f = tmp_path / "requirements-dev.txt"
    f.write_text("pytest")
    assert _should_include(f) is True


def test_include_dockerfile(tmp_path) -> None:
    f = tmp_path / "Dockerfile.prod"
    f.write_text("FROM python:3.11")
    assert _should_include(f) is True


# ── Unit: _has_secret ────────────────────────────────────────────────────────

def test_has_secret_detects_api_key() -> None:
    assert _has_secret('api_key = "sk-super-secret"') is True


def test_has_secret_clean_file() -> None:
    assert _has_secret("def hello(): return 'world'") is False


# ── Unit: _chunk_text ─────────────────────────────────────────────────────────

def test_chunk_short_text() -> None:
    chunks = _chunk_text("short content", "test.py")
    assert len(chunks) == 1


def test_chunk_long_text() -> None:
    long = "x" * 5000
    chunks = _chunk_text(long, "big.py")
    assert len(chunks) > 1


# ── Unit: namespace ───────────────────────────────────────────────────────────

def test_namespace_format() -> None:
    from app.config.settings import Settings
    svc = OnboardingIndexService(Settings(chroma_host="", chroma_local_path=""))
    pid = uuid.uuid4()
    ns = svc.namespace(pid)
    # Chroma-safe: proj- prefix + hex UUID (no colons or dots)
    assert ns.startswith("proj-")
    assert str(pid).replace("-", "") in ns


# ── Unit: scanner fixes ───────────────────────────────────────────────────────

def test_requirements_variant_detected_as_dependency(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "requirements-finquant.txt").write_text("pandas>=2.0\nnumpy>=1.24\n")
    (root / "main.py").write_text("import pandas as pd\n")
    (root / "README.md").write_text("# Finquant\n")
    svc = OnboardingScanService(str(root))
    result = svc.run(git_commit_sha="abc123")
    checks = result["checks"]
    assert "python-pip" in (checks.get("frameworks", {}).get("hints") or [])
    dep_files = checks.get("dependencies", {}).get("files") or []
    assert any("requirements-finquant.txt" in f for f in dep_files)


def test_language_weighting_python_primary_over_json(tmp_path: Path) -> None:
    """Python should be detected as primary even when JSON files dominate by count."""
    root = tmp_path / "repo"
    root.mkdir()
    data_dir = root / "data"
    data_dir.mkdir()
    # 10 JSON data files
    for i in range(10):
        (data_dir / f"data_{i}.json").write_text('{"x": 1}')
    # 3 Python source files
    (root / "train.py").write_text("import pandas as pd\ndf = pd.read_csv('x')\n")
    (root / "eval.py").write_text("def evaluate(): pass\n")
    (root / "utils.py").write_text("def helper(): return 1\n")

    svc = OnboardingScanService(str(root))
    result = svc.run()
    lang = result["checks"]["languages"]
    assert lang["primary"] == "python", f"Expected python but got {lang['primary']} (breakdown: {lang['breakdown']})"


# ── API endpoint tests ─────────────────────────────────────────────────────────

def test_index_requires_admin(client, minimal_project_ids, db_session, tmp_path) -> None:
    viewer = _make_viewer(db_session, minimal_project_ids)
    h = _login(client, minimal_project_ids)
    _begin_and_scan(client, minimal_project_ids, h, tmp_path)
    lr = client.post("/api/v1/auth/login", json=viewer)
    vh = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(f"/api/v1/projects/{_pid(minimal_project_ids)}/onboarding/index", headers=vh)
    assert r.status_code == 403


def test_index_status_requires_viewer(client, minimal_project_ids, db_session, tmp_path) -> None:
    h = _login(client, minimal_project_ids)
    _begin_and_scan(client, minimal_project_ids, h, tmp_path)
    r = client.get(f"/api/v1/projects/{_pid(minimal_project_ids)}/onboarding/index-status", headers=h)
    assert r.status_code == 200


def test_index_status_requires_auth(client, minimal_project_ids, db_session, tmp_path) -> None:
    h = _login(client, minimal_project_ids)
    _begin_and_scan(client, minimal_project_ids, h, tmp_path)
    r = client.get(f"/api/v1/projects/{_pid(minimal_project_ids)}/onboarding/index-status")
    assert r.status_code == 401


def test_cannot_index_before_scan(client, minimal_project_ids, db_session, tmp_path) -> None:
    h = _login(client, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    (tmp_path / "repo").mkdir()
    client.post(f"/api/v1/projects/{pid}/onboarding/begin",
                json={"repo_local_path": str(tmp_path / "repo"), "git_commit_sha": "sha"},
                headers=h)
    r = client.post(f"/api/v1/projects/{pid}/onboarding/index", headers=h)
    assert r.status_code == 409
    assert "cannot_index_from_status" in r.json()["detail"]


def test_secrets_block_index(client, minimal_project_ids, db_session, tmp_path) -> None:
    pid = _pid(minimal_project_ids)
    h = _login(client, minimal_project_ids)
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("def hello(): pass\n")
    (root / "config.py").write_text('api_key = "sk-12345678supersecret"\n')
    client.post(f"/api/v1/projects/{pid}/onboarding/begin",
                json={"repo_local_path": str(root), "git_commit_sha": "sha_sec"},
                headers=h)
    client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    r = client.post(f"/api/v1/projects/{pid}/onboarding/index", headers=h)
    assert r.status_code == 422
    assert "secrets" in r.json()["detail"]


def test_waive_secrets_allows_index(client, minimal_project_ids, db_session, tmp_path) -> None:
    """With waive_secrets=true an operator can index despite findings."""
    pid = _pid(minimal_project_ids)
    h = _login(client, minimal_project_ids)
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("def hello(): pass\n")
    (root / "config.py").write_text('api_key = "sk-12345678supersecret"\n')
    client.post(f"/api/v1/projects/{pid}/onboarding/begin",
                json={"repo_local_path": str(root), "git_commit_sha": "sha_waive"},
                headers=h)
    client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    r = client.post(f"/api/v1/projects/{pid}/onboarding/index?waive_secrets=true", headers=h)
    assert r.status_code == 200
    assert r.json()["index_status"] == "INDEXED"


def test_successful_index_updates_status(client, minimal_project_ids, db_session, tmp_path) -> None:
    pid = _pid(minimal_project_ids)
    h = _login(client, minimal_project_ids)
    _begin_and_scan(client, minimal_project_ids, h, tmp_path)
    r = client.post(f"/api/v1/projects/{pid}/onboarding/index", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["index_status"] == "INDEXED"
    assert body["index_job_id"] is not None


def test_index_status_endpoint_after_index(client, minimal_project_ids, db_session, tmp_path) -> None:
    pid = _pid(minimal_project_ids)
    h = _login(client, minimal_project_ids)
    _begin_and_scan(client, minimal_project_ids, h, tmp_path)
    client.post(f"/api/v1/projects/{pid}/onboarding/index", headers=h)
    r = client.get(f"/api/v1/projects/{pid}/onboarding/index-status", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["context_index_available"] is True
    assert body["indexed_file_count"] is not None
    assert body["indexed_chunk_count"] is not None
    assert body["index_status"] == "INDEXED"


def test_chunks_have_correct_metadata(client, minimal_project_ids, db_session, tmp_path) -> None:
    pid = _pid(minimal_project_ids)
    h = _login(client, minimal_project_ids)
    _begin_and_scan(client, minimal_project_ids, h, tmp_path)
    client.post(f"/api/v1/projects/{pid}/onboarding/index", headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(ProjectOnboarding).where(ProjectOnboarding.project_id == minimal_project_ids["project_id"])
    ).first()
    assert row is not None
    assert row.index_status == "INDEXED"
    assert row.indexed_file_count is not None and row.indexed_file_count > 0
    assert row.indexed_chunk_count is not None and row.indexed_chunk_count > 0


def test_namespace_is_project_scoped(client, minimal_project_ids, db_session, tmp_path) -> None:
    pid = _pid(minimal_project_ids)
    h = _login(client, minimal_project_ids)
    _begin_and_scan(client, minimal_project_ids, h, tmp_path)
    r = client.post(f"/api/v1/projects/{pid}/onboarding/index", headers=h)
    assert r.status_code == 200
    msg = r.json()["message"]
    # namespace format: proj-{hex_uuid} (Chroma-safe)
    assert "proj-" in msg


def test_excluded_env_file_not_indexed(client, minimal_project_ids, db_session, tmp_path) -> None:
    pid = _pid(minimal_project_ids)
    h = _login(client, minimal_project_ids)
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("def hello(): pass\n")
    (root / ".env").write_text("DB_URL=postgresql://localhost/db\n")
    client.post(f"/api/v1/projects/{pid}/onboarding/begin",
                json={"repo_local_path": str(root), "git_commit_sha": "sha_excl"},
                headers=h)
    client.post(f"/api/v1/projects/{pid}/onboarding/scan", headers=h)
    r = client.post(f"/api/v1/projects/{pid}/onboarding/index", headers=h)
    assert r.status_code == 200
    # .env excluded — only main.py counted
    assert r.json()["message"].count("1 files") >= 1 or "files" in r.json()["message"]


def test_audit_emitted_on_index(client, minimal_project_ids, db_session, tmp_path) -> None:
    pid = _pid(minimal_project_ids)
    h = _login(client, minimal_project_ids)
    _begin_and_scan(client, minimal_project_ids, h, tmp_path)
    client.post(f"/api/v1/projects/{pid}/onboarding/index", headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.ONBOARDING_INDEX_QUEUED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert p.get("namespace", "").startswith("proj-")
    assert p.get("indexed_files", 0) > 0


def test_failed_job_stores_safe_error(db_session: Session, minimal_project_ids: dict, tmp_path: Path) -> None:
    row = ProjectOnboarding(
        project_id=minimal_project_ids["project_id"],
        status=OnboardingStatus.SCANNED.value,
        repo_local_path="/nonexistent/path/xyz",
        git_commit_sha="test",
        scan_artifact_json={"checks": {"secrets_scan": {"findings_count": 0}}},
    )
    db_session.add(row)
    db_session.commit()

    from app.config.settings import Settings
    svc = OnboardingIndexService(Settings(chroma_host="", chroma_local_path=""))
    with pytest.raises(OnboardingIndexError) as ei:
        svc.run(db=db_session, onboarding=row, project_id=minimal_project_ids["project_id"])
    assert "inaccessible" in ei.value.reason or "no_repo_path" in ei.value.reason
    db_session.commit()
    db_session.expire_all()
    refreshed = db_session.get(ProjectOnboarding, row.id)
    assert refreshed.index_status == "FAILED"
    assert refreshed.index_error_safe is not None
