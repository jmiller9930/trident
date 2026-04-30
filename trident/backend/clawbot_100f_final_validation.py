#!/usr/bin/env python3
"""
100F final clawbot validation — MCP proofs over HTTP + DB receipts + optional post-restart LOW.

Usage (on clawbot, after compose up):
  docker compose exec trident-api python clawbot_100f_final_validation.py

After `docker compose restart trident-api`:
  docker compose exec -e TRIDENT_100F_DIRECTIVE_ID=... -e TRIDENT_100F_TASK_ID=... trident-api \\
    python clawbot_100f_final_validation.py --phase restart-low

Env:
  TRIDENT_PROOF_HTTP_HOST  default 127.0.0.1
  TRIDENT_PROOF_HTTP_PORT  default TRIDENT_API_PORT / 8000
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections import Counter

import httpx
from sqlalchemy import func, select

from app.config.settings import Settings
from app.db.session import session_factory_for_settings
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType, ProofObjectType
from app.models.project import Project
from app.models.proof_object import ProofObject
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _api_v1_base(cfg: Settings) -> str:
    host = os.environ.get("TRIDENT_PROOF_HTTP_HOST", "127.0.0.1")
    port = os.environ.get("TRIDENT_PROOF_HTTP_PORT", str(cfg.api_port))
    prefix = cfg.api_router_prefix.rstrip("/")
    return f"http://{host}:{port}{prefix}/v1"


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


def _bootstrap_directive(session) -> tuple[uuid.UUID, uuid.UUID]:
    user_id, workspace_id, project_id = _ensure_seed(session)
    body = CreateDirectiveRequest(
        workspace_id=workspace_id,
        project_id=project_id,
        title="100F FINAL clawbot validation",
        graph_id="mcp-f-final",
        created_by_user_id=user_id,
    )
    d, ledger, _gs = DirectiveRepository(session).create_directive_and_initialize(body)
    session.commit()
    return d.id, ledger.id


def _mcp_ctx(directive_id: uuid.UUID, task_id: uuid.UUID, *, command: str) -> dict:
    """Match architect curl: lowercase engineer."""
    return {
        "directive_id": str(directive_id),
        "task_id": str(task_id),
        "agent_role": "engineer",
        "command": command,
        "target": "local",
    }


def _db_mcp_snapshot(session, directive_id: uuid.UUID) -> tuple[int, Counter[str], int]:
    proof_count = session.scalar(
        select(func.count())
        .select_from(ProofObject)
        .where(
            ProofObject.directive_id == directive_id,
            ProofObject.proof_type == ProofObjectType.EXECUTION_LOG.value,
        )
    )
    proof_count = int(proof_count or 0)

    rows = session.scalars(
        select(AuditEvent).where(
            AuditEvent.directive_id == directive_id,
            AuditEvent.event_type.in_(
                [
                    AuditEventType.MCP_EXECUTION_REQUESTED.value,
                    AuditEventType.MCP_EXECUTION_COMPLETED.value,
                    AuditEventType.MCP_EXECUTION_REJECTED.value,
                ]
            ),
        )
    ).all()
    types = Counter(r.event_type for r in rows)
    return proof_count, types, len(rows)


def phase_restart_low(cfg: Settings, directive_id: uuid.UUID, task_id: uuid.UUID) -> int:
    base = _api_v1_base(cfg)
    ctx = _mcp_ctx(directive_id, task_id, command="pytest -q")
    with httpx.Client(timeout=60.0) as client:
        r = client.post(f"{base}/mcp/execute", json={**ctx, "explicitly_approved": False})
    print(f"restart_low_execute_status={r.status_code}")
    if r.status_code != 200:
        print(r.text, file=sys.stderr)
        return 1
    body = r.json()
    print(f"restart_low_proof_object_id={body.get('proof_object_id')} risk={body.get('risk')}")
    print("100f_final_restart_low_ok=1")
    return 0


def phase_full(cfg: Settings) -> int:
    SessionLocal = session_factory_for_settings(cfg)
    with SessionLocal() as session:
        directive_id, task_id = _bootstrap_directive(session)

    base = _api_v1_base(cfg)
    print(f"api_v1_base={base}")
    print(f"directive_id={directive_id}")
    print(f"task_id={task_id}")
    print(f"export TRIDENT_100F_DIRECTIVE_ID={directive_id}")
    print(f"export TRIDENT_100F_TASK_ID={task_id}")

    with httpx.Client(timeout=120.0) as client:
        # 1. Classification (HTTP)
        ctx_low = _mcp_ctx(directive_id, task_id, command="pytest")
        r1 = client.post(f"{base}/mcp/classify", json=ctx_low)
        print(f"classify_status={r1.status_code} body={r1.text}")
        if r1.status_code != 200:
            return 2
        if r1.json().get("risk") != "LOW":
            print("expected LOW from classify", file=sys.stderr)
            return 2

        # 2. LOW execution
        r2 = client.post(f"{base}/mcp/execute", json={**ctx_low, "explicitly_approved": False})
        print(f"low_execute_status={r2.status_code}")
        if r2.status_code != 200:
            print(r2.text, file=sys.stderr)
            return 3
        low_proof = uuid.UUID(r2.json()["proof_object_id"])

        # 3. HIGH rejection
        ctx_hi = _mcp_ctx(directive_id, task_id, command="trident_force_high")
        r3 = client.post(f"{base}/mcp/execute", json={**ctx_hi, "explicitly_approved": False})
        print(f"high_reject_status={r3.status_code} detail={r3.text}")
        if r3.status_code != 403:
            return 4
        try:
            detail = r3.json().get("detail")
            if isinstance(detail, dict):
                if detail.get("code") != "high_risk_not_approved":
                    print("expected high_risk_not_approved", file=sys.stderr)
                    return 4
                hi_block_proof = uuid.UUID(str(detail["proof_object_id"]))
            else:
                print("expected structured 403 detail", file=sys.stderr)
                return 4
        except (KeyError, TypeError, ValueError) as e:
            print(f"parse 403 detail failed: {e}", file=sys.stderr)
            return 4

        # 4. HIGH approved
        r4 = client.post(f"{base}/mcp/execute", json={**ctx_hi, "explicitly_approved": True})
        print(f"high_approved_status={r4.status_code}")
        if r4.status_code != 200:
            print(r4.text, file=sys.stderr)
            return 5
        hi_ok_proof = uuid.UUID(r4.json()["proof_object_id"])

    # 5. DB validation
    with SessionLocal() as session:
        proof_count, type_counts, audit_rows = _db_mcp_snapshot(session, directive_id)

        for pid in (low_proof, hi_block_proof, hi_ok_proof):
            p = session.get(ProofObject, pid)
            if p is None or p.proof_type != ProofObjectType.EXECUTION_LOG.value:
                print(f"proof row missing or wrong type for {pid}", file=sys.stderr)
                return 6

        req_n = type_counts.get(AuditEventType.MCP_EXECUTION_REQUESTED.value, 0)
        done_n = type_counts.get(AuditEventType.MCP_EXECUTION_COMPLETED.value, 0)
        rej_n = type_counts.get(AuditEventType.MCP_EXECUTION_REJECTED.value, 0)

        print(f"proof_objects_exec_log_count={proof_count}")
        print(f"mcp_audit_requested={req_n} completed={done_n} rejected={rej_n} total_mcp_rows={audit_rows}")

        if req_n != 3:
            print("expected 3 MCP_EXECUTION_REQUESTED", file=sys.stderr)
            return 6
        if done_n != 2:
            print("expected 2 MCP_EXECUTION_COMPLETED", file=sys.stderr)
            return 6
        if rej_n != 1:
            print("expected 1 MCP_EXECUTION_REJECTED", file=sys.stderr)
            return 6

        # Ordering: last three REQUESTED indices vs COMPLETED/REJECTED — loose check: exactly one REJECTED ever
        rejects = [
            r
            for r in session.scalars(
                select(AuditEvent).where(
                    AuditEvent.directive_id == directive_id,
                    AuditEvent.event_type == AuditEventType.MCP_EXECUTION_REJECTED.value,
                )
            ).all()
        ]
        if len(rejects) != 1:
            print(f"expected exactly one REJECTED audit, got {len(rejects)}", file=sys.stderr)
            return 6

    print("")
    print("--- Post-restart check ---")
    print("docker compose restart trident-api")
    print(
        "docker compose exec -e TRIDENT_100F_DIRECTIVE_ID=%s -e TRIDENT_100F_TASK_ID=%s trident-api "
        "python clawbot_100f_final_validation.py --phase restart-low" % (directive_id, task_id)
    )

    print("100f_final_validation_ok=1")
    return 0


def main() -> int:
    cfg = Settings()
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=("full", "restart-low"), default="full")
    args = p.parse_args()

    if args.phase == "restart-low":
        ds = os.environ.get("TRIDENT_100F_DIRECTIVE_ID")
        ts = os.environ.get("TRIDENT_100F_TASK_ID")
        if not ds or not ts:
            print("missing TRIDENT_100F_DIRECTIVE_ID or TRIDENT_100F_TASK_ID", file=sys.stderr)
            return 99
        return phase_restart_low(cfg, uuid.UUID(ds), uuid.UUID(ts))

    return phase_full(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
