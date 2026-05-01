"""100M — patch propose / reject / apply-complete (lock + Git authority)."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType, ProofObjectType
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
        title="100M patch directive",
        graph_id="100m-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


def _base(proj, did, uid, before: str, after: str, path: str = "tracked.txt"):
    return {
        "project_id": str(proj.id),
        "directive_id": str(did),
        "agent_role": "ENGINEER",
        "user_id": str(uid),
        "file_path": path,
        "before_text": before,
        "after_text": after,
    }


def test_patch_propose_returns_unified_diff(client: TestClient, db_session, minimal_project_ids, tmp_path: Path) -> None:
    repo = tmp_path / "pm1"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    r = client.post("/api/v1/patches/propose", json=_base(proj, did, uid, "hello\n", "hello\nworld\n"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "--- a/tracked.txt" in body["unified_diff"]
    assert "+++ b/tracked.txt" in body["unified_diff"]
    assert body["result_text"] == "hello\nworld\n"
    assert "correlation_id" in body

    n = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.PATCH_PROPOSED.value)
    )
    assert int(n or 0) >= 1


def test_patch_propose_rejects_hidden_path(client: TestClient, db_session, minimal_project_ids, tmp_path: Path) -> None:
    repo = tmp_path / "pm2"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    p = _base(proj, did, uid, "a", "b", path=".env")
    r = client.post("/api/v1/patches/propose", json=p)
    assert r.status_code == 400
    assert r.json()["detail"] == "hidden_path_segment_forbidden"


def test_patch_reject_audits(client: TestClient, db_session, minimal_project_ids, tmp_path: Path) -> None:
    repo = tmp_path / "pm3"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    before = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.PATCH_REJECTED.value)
    )
    r = client.post(
        "/api/v1/patches/reject",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
            "reason": "no thanks",
        },
    )
    assert r.status_code == 200, r.text
    after = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.PATCH_REJECTED.value)
    )
    assert int(after or 0) == int(before or 0) + 1


def test_patch_apply_complete_blocked_without_lock(client: TestClient, db_session, minimal_project_ids, tmp_path: Path) -> None:
    repo = tmp_path / "pm4"
    repo.mkdir()
    _git_init_commit(repo)
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _directive(client, db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    prop = client.post("/api/v1/patches/propose", json=_base(proj, did, uid, "hello\n", "hello\npatched\n"))
    assert prop.status_code == 200
    diff = prop.json()["unified_diff"]
    after_text = prop.json()["result_text"]
    cid = prop.json()["correlation_id"]

    (repo / "tracked.txt").write_text(after_text, encoding="utf-8")

    r = client.post(
        "/api/v1/patches/apply-complete",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
            "unified_diff": diff,
            "after_text": after_text,
            "correlation_id": cid,
        },
    )
    assert r.status_code == 404


def test_patch_apply_complete_success(client: TestClient, db_session, minimal_project_ids, tmp_path: Path) -> None:
    repo = tmp_path / "pm5"
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

    prop = client.post("/api/v1/patches/propose", json=_base(proj, did, uid, "hello\n", "hello\npatched\n"))
    assert prop.status_code == 200
    diff = prop.json()["unified_diff"]
    after_text = prop.json()["result_text"]
    cid = prop.json()["correlation_id"]

    (repo / "tracked.txt").write_text(after_text, encoding="utf-8")

    before_applied = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.PATCH_APPLIED.value)
    )

    r = client.post(
        "/api/v1/patches/apply-complete",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
            "unified_diff": diff,
            "after_text": after_text,
            "correlation_id": cid,
        },
    )
    assert r.status_code == 200, r.text
    pid = uuid.UUID(r.json()["proof_object_id"])
    proof = db_session.get(ProofObject, pid)
    assert proof is not None
    assert proof.proof_type == ProofObjectType.GIT_DIFF.value
    assert diff in proof.proof_summary or proof.proof_summary == diff

    after_applied = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.PATCH_APPLIED.value)
    )
    assert int(after_applied or 0) == int(before_applied or 0) + 1


def test_patch_apply_complete_disk_mismatch(client: TestClient, db_session, minimal_project_ids, tmp_path: Path) -> None:
    repo = tmp_path / "pm6"
    repo.mkdir()
    _git_init_commit(repo)
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
            "file_path": "tracked.txt",
        },
    )
    prop = client.post("/api/v1/patches/propose", json=_base(proj, did, uid, "hello\n", "hello\npatched\n"))
    diff = prop.json()["unified_diff"]
    after_text = prop.json()["result_text"]
    (repo / "tracked.txt").write_text("wrong on disk\n", encoding="utf-8")

    r = client.post(
        "/api/v1/patches/apply-complete",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": "tracked.txt",
            "unified_diff": diff,
            "after_text": after_text,
        },
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "patch_disk_verification_failed"
