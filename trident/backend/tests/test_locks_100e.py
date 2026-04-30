"""100E — Git read-only + file locks + simulated mutation pipeline."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType, ProofObjectType
from app.models.file_lock import FileLock
from app.models.project import Project
from app.models.proof_object import ProofObject
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _git_init_commit(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "e@test.local"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True)
    (repo / "tracked.txt").write_text("hello\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)


def _directive(client: TestClient, db_session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="100E lock directive",
        graph_id="100e-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


def test_lock_acquire_and_release(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()

    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    r1 = client.post(
        "/api/v1/locks/acquire",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
        },
    )
    assert r1.status_code == 200, r1.text
    lid = r1.json()["lock_id"]

    r2 = client.post(
        "/api/v1/locks/release",
        json={
            "lock_id": lid,
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
        },
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["lock_status"] == "RELEASED"


def test_lock_conflict_second_acquire(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path: Path) -> None:
    repo = tmp_path / "r2"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    p = {"project_id": str(proj.id), "directive_id": str(did), "agent_role": "ENGINEER", "user_id": str(uid), "file_path": "tracked.txt"}
    assert client.post("/api/v1/locks/acquire", json=p).status_code == 200
    before_rej = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.LOCK_REJECTED.value)
    )
    r = client.post("/api/v1/locks/acquire", json=p)
    assert r.status_code == 409
    after_rej = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.LOCK_REJECTED.value)
    )
    assert int(after_rej or 0) >= int(before_rej or 0) + 1


def test_release_ownership_mismatch(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path: Path) -> None:
    repo = tmp_path / "r3"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    r1 = client.post(
        "/api/v1/locks/acquire",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
        },
    )
    lid = r1.json()["lock_id"]
    bad_user = str(uuid.uuid4())
    r2 = client.post(
        "/api/v1/locks/release",
        json={
            "lock_id": lid,
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": bad_user,
            "file_path": "tracked.txt",
        },
    )
    assert r2.status_code == 403


def test_git_repo_validation_failure_not_git(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path: Path) -> None:
    repo = tmp_path / "nogit"
    repo.mkdir()
    (repo / "x.txt").write_text("x")
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    client.post(
        "/api/v1/locks/acquire",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "x.txt",
        },
    )
    r = client.post(
        "/api/v1/locks/simulated-mutation",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "x.txt",
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "not_a_git_repository"


def test_path_traversal_rejected(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    r = client.post(
        "/api/v1/locks/acquire",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "../outside.txt",
        },
    )
    assert r.status_code == 400


def test_simulated_mutation_proof_and_audits(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path: Path) -> None:
    repo = tmp_path / "r4"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    assert (
        client.post(
            "/api/v1/locks/acquire",
            json={
                "project_id": str(proj.id),
                "directive_id": str(did),
                "agent_role": "ENGINEER",
                "user_id": str(uid),
                "file_path": "tracked.txt",
            },
        ).status_code
        == 200
    )

    before_git = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.GIT_STATUS_CHECKED.value)
    )
    before_diff = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.DIFF_GENERATED.value)
    )

    r = client.post(
        "/api/v1/locks/simulated-mutation",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
        },
    )
    assert r.status_code == 200, r.text
    pid = r.json()["proof_object_id"]
    proof = db_session.get(ProofObject, uuid.UUID(pid))
    assert proof is not None
    assert proof.proof_type == ProofObjectType.GIT_DIFF.value
    assert proof.directive_id == did

    after_git = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.GIT_STATUS_CHECKED.value)
    )
    after_diff = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.DIFF_GENERATED.value)
    )
    assert int(after_git or 0) == int(before_git or 0) + 1
    assert int(after_diff or 0) == int(before_diff or 0) + 1


def test_simulated_mutation_requires_prior_lock(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path: Path) -> None:
    repo = tmp_path / "r5"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    r = client.post(
        "/api/v1/locks/simulated-mutation",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
        },
    )
    assert r.status_code == 404


def test_lock_persistence_across_sessions(client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path: Path) -> None:
    repo = tmp_path / "r6"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    r = client.post(
        "/api/v1/locks/acquire",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
        },
    )
    assert r.status_code == 200
    lid = uuid.UUID(r.json()["lock_id"])

    bind = db_session.get_bind()
    Session2 = sessionmaker(bind=bind)
    s2 = Session2()
    try:
        row = s2.get(FileLock, lid)
        assert row is not None
        assert row.lock_status == "ACTIVE"
    finally:
        s2.close()
