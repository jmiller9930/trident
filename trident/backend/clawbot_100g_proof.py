#!/usr/bin/env python3
"""100G clawbot proof: HTTP POST /router/route only; counts ROUTER_DECISION_MADE audits."""

from __future__ import annotations

import os
import sys
import uuid

import httpx
from sqlalchemy import func, select

from app.config.settings import Settings
from app.db.session import create_engine_for_settings, session_factory_for_settings
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
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
    proj = session.scalar(select(Project).where(Project.workspace_id == ws.id).limit(1))
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


def _api_v1_base(cfg: Settings) -> str:
    host = os.environ.get("TRIDENT_PROOF_HTTP_HOST", "127.0.0.1")
    port = os.environ.get("TRIDENT_PROOF_HTTP_PORT", str(cfg.api_port))
    prefix = cfg.api_router_prefix.rstrip("/")
    return f"http://{host}:{port}{prefix}/v1"


def main() -> int:
    cfg = Settings()
    SessionLocal = session_factory_for_settings(create_engine_for_settings(cfg))
    with SessionLocal() as session:
        uid, wsid, pid = _ensure_seed(session)
        body = CreateDirectiveRequest(
            workspace_id=wsid,
            project_id=pid,
            title="100G clawbot proof",
            graph_id="r100g-proof",
            created_by_user_id=uid,
        )
        d, ledger, _gs = DirectiveRepository(session).create_directive_and_initialize(body)
        session.commit()
        did, tid = d.id, ledger.id

    base = _api_v1_base(cfg)
    ctx = lambda intent: {  # noqa: E731
        "directive_id": str(did),
        "task_id": str(tid),
        "agent_role": "ENGINEER",
        "intent": intent,
        "payload": {},
    }

    intents_ok = [
        ("route.memory", "MEMORY"),
        ("route.mcp", "MCP"),
        ("route.langgraph", "LANGGRAPH"),
        ("route.nike", "NIKE"),
    ]

    with httpx.Client(timeout=60.0) as client:
        for intent, route in intents_ok:
            r = client.post(f"{base}/router/route", json=ctx(intent))
            print(f"route_{intent}_status={r.status_code}")
            if r.status_code != 200:
                print(r.text, file=sys.stderr)
                return 1
            j = r.json()
            if not j.get("validated") or j.get("route") != route:
                print(j, file=sys.stderr)
                return 2

        r_amb = client.post(f"{base}/router/route", json=ctx("mcp_execute memory_read conflict"))
        print(f"ambiguous_status={r_amb.status_code}")
        if r_amb.status_code != 200:
            return 3
        ja = r_amb.json()
        if ja.get("validated") is not False:
            print(ja, file=sys.stderr)
            return 4

    with SessionLocal() as session:
        n = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.directive_id == did,
                AuditEvent.event_type == AuditEventType.ROUTER_DECISION_MADE.value,
            )
        )
        print(f"router_decision_made_count={int(n or 0)}")
        if int(n or 0) < 5:
            return 5

    print("100g_clawbot_proof_ok=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
