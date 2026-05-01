"""FIX 003 — heartbeat, staleness, recovery, force-release."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config.settings import Settings
from app.db.session import get_db
from app.main import build_app
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.file_lock import FileLock
from app.models.project import Project
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _make_directive(db_session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="FIX003 directive",
        graph_id="fix003-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    return d.id


@pytest.fixture
def hb_client(sqlite_engine):
    SessionLocal = sessionmaker(bind=sqlite_engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app = build_app(
        Settings(
            base_path="",
            lock_heartbeat_miss_sec=2,
            lock_force_release_admin_user_ids="",
        )
    )
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def _acquire(client, proj, did, uid, path: str) -> dict:
    r = client.post(
        "/api/v1/locks/acquire",
        json={
            "project_id": str(proj),
            "directive_id": str(did),
            "agent_role": "ENGINEER",
            "user_id": str(uid),
            "file_path": path,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def _hb_body(lid, proj, did, uid, path: str) -> dict:
    return {
        "lock_id": str(lid),
        "project_id": str(proj),
        "directive_id": str(did),
        "agent_role": "ENGINEER",
        "user_id": str(uid),
        "file_path": path,
    }


def test_heartbeat_refreshes_and_prevents_stale(
    hb_client: TestClient, db_session, minimal_project_ids, tmp_path
) -> None:
    repo = tmp_path / "h1"
    repo.mkdir()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _make_directive(db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]
    a = _acquire(hb_client, proj.id, did, uid, "a.txt")
    lid = a["lock_id"]

    st = hb_client.get("/api/v1/locks/status", params={"project_id": str(proj.id), "file_path": "a.txt"})
    assert st.status_code == 200
    assert st.json()["lock_status"] == "ACTIVE"

    r = hb_client.post("/api/v1/locks/heartbeat", json=_hb_body(lid, proj.id, did, uid, "a.txt"))
    assert r.status_code == 200, r.text
    n = db_session.scalars(select(AuditEvent).where(AuditEvent.event_type == AuditEventType.LOCK_HEARTBEAT.value)).all()
    assert len(n) >= 1


def test_missed_heartbeat_makes_get_active_404(
    hb_client: TestClient, db_session, minimal_project_ids, tmp_path
) -> None:
    repo = tmp_path / "h2"
    repo.mkdir()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _make_directive(db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]
    a = _acquire(hb_client, proj.id, did, uid, "b.txt")
    lid = a["lock_id"]
    lock = db_session.get(FileLock, uuid.UUID(lid))
    assert lock is not None
    lock.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db_session.commit()

    g = hb_client.get(
        "/api/v1/locks/active",
        params={"project_id": str(proj.id), "file_path": "b.txt"},
    )
    assert g.status_code == 404

    st = hb_client.get("/api/v1/locks/status", params={"project_id": str(proj.id), "file_path": "b.txt"})
    assert st.status_code == 200
    assert st.json()["lock_status"] == "STALE_PENDING_RECOVERY"


def test_release_from_stale_succeeds(
    hb_client: TestClient, db_session, minimal_project_ids, tmp_path
) -> None:
    repo = tmp_path / "h3"
    repo.mkdir()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _make_directive(db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]
    a = _acquire(hb_client, proj.id, did, uid, "c.txt")
    lid = a["lock_id"]
    lock = db_session.get(FileLock, uuid.UUID(lid))
    assert lock is not None
    lock.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db_session.commit()

    rel = hb_client.post(
        "/api/v1/locks/release",
        json=_hb_body(lid, proj.id, did, uid, "c.txt"),
    )
    assert rel.status_code == 200, rel.text
    db_session.refresh(lock)
    assert lock.lock_status == "RELEASED"


def test_force_release_allowlist(
    hb_client: TestClient, db_session, minimal_project_ids, tmp_path
) -> None:
    admin_id = uuid.uuid4()
    SessionLocal = sessionmaker(bind=db_session.get_bind())

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app = build_app(
        Settings(
            base_path="",
            lock_heartbeat_miss_sec=0,
            lock_force_release_admin_user_ids=str(admin_id),
        )
    )
    app.dependency_overrides[get_db] = override_get_db

    repo = tmp_path / "h4"
    repo.mkdir()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did = _make_directive(db_session, minimal_project_ids)
    uid = minimal_project_ids["user_id"]

    with TestClient(app) as client:
        a = _acquire(client, proj.id, did, uid, "d.txt")
        lid = a["lock_id"]

        r403 = client.post(
            "/api/v1/locks/force-release",
            json={"lock_id": lid, "project_id": str(proj.id), "admin_user_id": str(uuid.uuid4())},
        )
        assert r403.status_code == 403

        r200 = client.post(
            "/api/v1/locks/force-release",
            json={"lock_id": lid, "project_id": str(proj.id), "admin_user_id": str(admin_id)},
        )
        assert r200.status_code == 200, r200.text
        assert r200.json()["lock_status"] == "FORCE_RELEASED"

    app.dependency_overrides.clear()


def test_acquire_after_stale_other_principal(
    hb_client: TestClient, db_session, minimal_project_ids, tmp_path
) -> None:
    """Stale lock from user A; user B acquires same path after takeover archive."""
    repo = tmp_path / "h5"
    repo.mkdir()
    proj = db_session.get(Project, minimal_project_ids["project_id"])
    assert proj is not None
    proj.allowed_root_path = str(repo.resolve())
    db_session.commit()
    did_a = _make_directive(db_session, minimal_project_ids)
    uid_a = minimal_project_ids["user_id"]

    did_b = _make_directive(db_session, minimal_project_ids)
    uid_b = uuid.uuid4()
    from app.models.user import User

    db_session.add(User(id=uid_b, display_name="B", email=f"b-{uid_b}@t.test", role="member"))
    db_session.commit()

    a = _acquire(hb_client, proj.id, did_a, uid_a, "e.txt")
    lid = a["lock_id"]
    lock = db_session.get(FileLock, uuid.UUID(lid))
    lock.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db_session.commit()

    b = hb_client.post(
        "/api/v1/locks/acquire",
        json={
            "project_id": str(proj.id),
            "directive_id": str(did_b),
            "agent_role": "ENGINEER",
            "user_id": str(uid_b),
            "file_path": "e.txt",
        },
    )
    assert b.status_code == 200, b.text
