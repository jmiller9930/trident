#!/usr/bin/env python3
"""100F clawbot proof: seed directive via DB, then HTTP classify + execute (simulated only)."""

from __future__ import annotations

import os
import sys
import uuid

import httpx
from sqlalchemy import select

from app.config.settings import Settings
from app.db.session import create_engine_for_settings, session_factory_for_settings
from app.models.project import Project
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _ensure_seed(session) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
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
    base = os.environ.get("TRIDENT_PROOF_API_BASE", "http://127.0.0.1:8000/api/v1").rstrip("/")
    cfg = Settings()
    engine = create_engine_for_settings(cfg)
    SessionLocal = session_factory_for_settings(cfg)

    with SessionLocal() as session:
        user_id, workspace_id, project_id = _ensure_seed(session)
        body = CreateDirectiveRequest(
            workspace_id=workspace_id,
            project_id=project_id,
            title="100F MCP clawbot proof",
            graph_id="mcp-f-proof",
            created_by_user_id=user_id,
        )
        d, ledger, _gs = DirectiveRepository(session).create_directive_and_initialize(body)
        session.commit()
        directive_id = str(d.id)
        task_id = str(ledger.id)

    ctx = {
        "directive_id": directive_id,
        "task_id": task_id,
        "agent_role": "ENGINEER",
        "command": "pytest -q",
        "target": "local",
    }

    with httpx.Client(timeout=60.0) as client:
        c = client.post(f"{base}/mcp/classify", json=ctx)
        print(f"classify_status={c.status_code} body={c.json() if c.headers.get('content-type','').startswith('application/json') else c.text}")
        if c.status_code != 200:
            return 2

        low = client.post(f"{base}/mcp/execute", json={**ctx, "explicitly_approved": False})
        print(f"execute_low_status={low.status_code}")
        if low.status_code != 200:
            print(low.text, file=sys.stderr)
            return 3

        high_ctx = {**ctx, "command": "trident_force_high clawbot"}
        hi_block = client.post(f"{base}/mcp/execute", json={**high_ctx, "explicitly_approved": False})
        print(f"execute_high_blocked_status={hi_block.status_code}")
        if hi_block.status_code != 403:
            print(hi_block.text, file=sys.stderr)
            return 4

        hi_ok = client.post(f"{base}/mcp/execute", json={**high_ctx, "explicitly_approved": True})
        print(f"execute_high_approved_status={hi_ok.status_code}")
        if hi_ok.status_code != 200:
            print(hi_ok.text, file=sys.stderr)
            return 5

        detail = hi_ok.json()
        print(f"proof_object_id={detail.get('proof_object_id')} adapter={detail.get('adapter')}")

    print("100f_clawbot_proof_ok=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
