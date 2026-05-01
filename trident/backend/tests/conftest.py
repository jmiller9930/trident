from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import build_app
from app.models import Project, User, Workspace
from app.models.enums import ProjectMemberRole
from app.models.project_member import ProjectMember
from app.security.passwords import hash_password

_TEST_PASSWORD = "testpassword123"


@pytest.fixture
def sqlite_engine():
    import app.models  # noqa: F401 — register metadata

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(sqlite_engine) -> Session:
    SessionLocal = sessionmaker(bind=sqlite_engine)
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client(sqlite_engine):
    SessionLocal = sessionmaker(bind=sqlite_engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except HTTPException:
            db.commit()
            raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # Ignore deploy TRIDENT_BASE_PATH (e.g. /trident on clawbot) so TestClient uses /api/* .
    app = build_app(Settings(base_path="", lock_heartbeat_miss_sec=0))
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


@pytest.fixture
def minimal_project_ids(db_session: Session) -> dict[str, uuid.UUID | str]:
    """One user, workspace, project + OWNER membership + password (JWT tests)."""
    u = uuid.uuid4()
    email = f"user-{u}@example.com"
    user = User(
        id=u,
        display_name="Test User",
        email=email,
        role="member",
        password_hash=hash_password(_TEST_PASSWORD),
    )
    db_session.add(user)
    db_session.flush()
    ws = Workspace(id=uuid.uuid4(), name="WS", description=None, created_by_user_id=user.id)
    db_session.add(ws)
    db_session.flush()
    proj = Project(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        name="Proj",
        allowed_root_path="/tmp/trident",
        git_remote_url=None,
    )
    db_session.add(proj)
    db_session.flush()
    db_session.add(
        ProjectMember(project_id=proj.id, user_id=user.id, role=ProjectMemberRole.OWNER.value),
    )
    db_session.commit()
    return {
        "user_id": user.id,
        "workspace_id": ws.id,
        "project_id": proj.id,
        "email": email,
        "password": _TEST_PASSWORD,
    }


@pytest.fixture
def auth_headers(client, minimal_project_ids):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": minimal_project_ids["email"], "password": minimal_project_ids["password"]},
    )
    assert r.status_code == 200, r.text
    token = r.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
