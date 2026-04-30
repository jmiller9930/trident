"""100P — GET /locks/active + TTL expiry behavior."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.config.settings import Settings
from app.db.session import get_db
from app.main import build_app
from app.models.file_lock import FileLock
from app.models.project import Project
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _make_directive(db_session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="100P lock active",
        graph_id="100p-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


@pytest.fixture
def ttl_client(sqlite_engine):
    SessionLocal = sessionmaker(bind=sqlite_engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app = build_app(Settings(base_path="", lock_ttl_sec=7200))
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def test_get_active_lock_returns_metadata(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path
) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _make_directive(db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]
    body = {
        "project_id": str(proj.id),
        "directive_id": str(did),
        "agent_role": "ENGINEER",
        "user_id": str(uid),
        "file_path": "foo.txt",
    }
    r = client.post("/api/v1/locks/acquire", json=body)
    assert r.status_code == 200, r.text

    g = client.get(
        "/api/v1/locks/active",
        params={"project_id": str(proj.id), "file_path": "foo.txt"},
    )
    assert g.status_code == 200, g.text
    js = g.json()
    assert js["file_path"] == "foo.txt"
    assert js["directive_id"] == str(did)
    assert js["locked_by_user_id"] == str(uid)


def test_get_active_lock_404_when_expired_row_present(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path
) -> None:
    repo = tmp_path / "r2"
    repo.mkdir()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _make_directive(db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]
    body = {
        "project_id": str(proj.id),
        "directive_id": str(did),
        "agent_role": "ENGINEER",
        "user_id": str(uid),
        "file_path": "bar.txt",
    }
    r = client.post("/api/v1/locks/acquire", json=body)
    assert r.status_code == 200, r.text
    lid = uuid.UUID(r.json()["lock_id"])

    lock = db_session.get(FileLock, lid)
    assert lock is not None
    lock.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    db_session.commit()

    g = client.get(
        "/api/v1/locks/active",
        params={"project_id": str(proj.id), "file_path": "bar.txt"},
    )
    assert g.status_code == 404


def test_acquire_after_ttl_expires_releases_stale_and_succeeds(
    client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path
) -> None:
    repo = tmp_path / "r3"
    repo.mkdir()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _make_directive(db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]
    body = {
        "project_id": str(proj.id),
        "directive_id": str(did),
        "agent_role": "ENGINEER",
        "user_id": str(uid),
        "file_path": "baz.txt",
    }
    r = client.post("/api/v1/locks/acquire", json=body)
    assert r.status_code == 200, r.text
    lid = uuid.UUID(r.json()["lock_id"])

    lock = db_session.get(FileLock, lid)
    assert lock is not None
    lock.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    r2 = client.post("/api/v1/locks/acquire", json=body)
    assert r2.status_code == 200, r2.text
    assert uuid.UUID(r2.json()["lock_id"]) != lid

    released_old = db_session.get(FileLock, lid)
    assert released_old is not None
    assert released_old.lock_status == "RELEASED"


def test_acquire_sets_expires_when_settings_ttl(
    ttl_client: TestClient, db_session, minimal_project_ids: dict[str, uuid.UUID], tmp_path
) -> None:
    repo = tmp_path / "r4"
    repo.mkdir()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _make_directive(db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]
    body = {
        "project_id": str(proj.id),
        "directive_id": str(did),
        "agent_role": "ENGINEER",
        "user_id": str(uid),
        "file_path": "ttl.txt",
    }
    r = ttl_client.post("/api/v1/locks/acquire", json=body)
    assert r.status_code == 200, r.text
    lid = uuid.UUID(r.json()["lock_id"])

    db_session.expire_all()
    lock = db_session.get(FileLock, lid)
    assert lock is not None
    assert lock.expires_at is not None
