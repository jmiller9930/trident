#!/usr/bin/env python3
"""100E clawbot proof: live Postgres + read-only git under Project.allowed_root_path."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.session import create_engine_for_settings, session_factory_for_settings
from app.locks.exceptions import LockConflictError
from app.locks.lock_service import LockService
from app.locks.simulated_mutation import SimulatedMutationPipeline
from app.models.audit_event import AuditEvent
from app.models.directive import Directive
from app.models.enums import AuditEventType
from app.models.file_lock import FileLock
from app.models.project import Project
from app.models.proof_object import ProofObject
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "proof@trident.local"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Trident Proof"], cwd=repo, check=True, capture_output=True)
    (repo / "proof.txt").write_text("seed\n")
    subprocess.run(["git", "add", "proof.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)


def _ensure_seed(session: Session) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    u = session.scalar(select(User).limit(1))
    if u is None:
        uid = uuid.uuid4()
        u = User(id=uid, display_name="Proof User", email=f"proof-{uid}@trident.local", role="member")
        session.add(u)
        session.flush()
    ws = session.scalar(select(Workspace).limit(1))
    if ws is None:
        ws = Workspace(id=uuid.uuid4(), name="Proof WS", description=None, created_by_user_id=u.id)
        session.add(ws)
        session.flush()
    proj = session.scalar(select(Project).limit(1))
    if proj is None:
        proj = Project(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            name="Proof Proj",
            allowed_root_path="/tmp",
            git_remote_url=None,
        )
        session.add(proj)
        session.flush()
    session.commit()
    return u.id, ws.id, proj.id


def main() -> int:
    cfg = Settings()
    engine = create_engine_for_settings(cfg)
    SessionLocal = session_factory_for_settings(cfg)

    repo_dir = Path(tempfile.mkdtemp(prefix="trident-100e-proof-"))
    _git_init(repo_dir)

    with SessionLocal() as session:
        user_id, workspace_id, project_id = _ensure_seed(session)

        proj = session.get(Project, project_id)
        assert proj is not None
        proj.allowed_root_path = str(repo_dir.resolve())
        session.commit()

        body = CreateDirectiveRequest(
            workspace_id=workspace_id,
            project_id=project_id,
            title="100E clawbot proof directive",
            graph_id="100e-proof",
            created_by_user_id=user_id,
        )
        d, _, _ = DirectiveRepository(session).create_directive_and_initialize(body)
        session.commit()
        directive_id = d.id

        locks = LockService(session)
        fp = "proof.txt"

        print("=== Lock acquire ===")
        lock_a = locks.acquire(
            project_id=project_id,
            directive_id=directive_id,
            agent_role="ENGINEER",
            user_id=user_id,
            relative_file_path=fp,
        )
        session.commit()
        print(f"lock_id={lock_a.id}")

        print("=== Conflict attempt ===")
        try:
            locks.acquire(
                project_id=project_id,
                directive_id=directive_id,
                agent_role="ENGINEER",
                user_id=user_id,
                relative_file_path=fp,
            )
            session.commit()
        except LockConflictError:
            print("conflict_rejected=OK")
        else:
            print("conflict_rejected=FAIL")
            return 1

        print("=== Release ===")
        locks.release(
            lock_id=lock_a.id,
            project_id=project_id,
            directive_id=directive_id,
            agent_role="ENGINEER",
            user_id=user_id,
            relative_file_path=fp,
        )
        session.commit()
        print("released=OK")

        print("=== Re-acquire for simulated mutation ===")
        lock_b = locks.acquire(
            project_id=project_id,
            directive_id=directive_id,
            agent_role="ENGINEER",
            user_id=user_id,
            relative_file_path=fp,
        )
        session.commit()
        print(f"lock_id={lock_b.id}")

        print("=== Simulated mutation ===")
        pipe = SimulatedMutationPipeline(session)
        out = pipe.run(
            project_id=project_id,
            directive_id=directive_id,
            agent_role="ENGINEER",
            user_id=user_id,
            relative_file_path=fp,
        )
        session.commit()
        proof_id = out["proof_object_id"]
        print(f"proof_object_id={proof_id}")

        proof = session.get(ProofObject, proof_id)
        assert proof is not None
        print(f"proof_type={proof.proof_type}")

        for et in (
            AuditEventType.GIT_STATUS_CHECKED,
            AuditEventType.DIFF_GENERATED,
        ):
            count = session.scalar(
                select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.directive_id == directive_id,
                    AuditEvent.event_type == et.value,
                )
            )
            print(f"audit_{et.value}_count={int(count or 0)}")

        print("=== Leave ACTIVE lock for restart persistence check ===")
        row = session.get(FileLock, lock_b.id)
        assert row is not None and row.lock_status == "ACTIVE"
        print(f"persistence_lock_id={lock_b.id}")

    print(f"repo_dir={repo_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
