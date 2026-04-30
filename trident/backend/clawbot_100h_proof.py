#!/usr/bin/env python3
"""100H clawbot proof: HTTP workflow/run → engineer agent phase; DB audit + memory + MCP receipt checks.

Run inside API container (Postgres + optional Chroma), same bar as 100E/100F/100G proofs.

Host bootstrap (from program message):
  docker compose exec trident-api python -m alembic upgrade head
  docker compose exec trident-api python clawbot_100h_proof.py

Post-restart verification (same DB must retain rows):
  docker compose restart trident-api
  docker compose exec trident-api env TRIDENT_100H_VERIFY_DIRECTIVE_ID=<uuid> python clawbot_100h_proof.py

Env:
  TRIDENT_PROOF_HTTP_HOST / TRIDENT_PROOF_HTTP_PORT — API reachability from script (default 127.0.0.1:8000).
  TRIDENT_GIT_HEAD — optional; image has no .git (set from host CI/clawbot).
  TRIDENT_100H_VERIFY_DIRECTIVE_ID — skip create/run; only DB validation (restart persistence).
"""

from __future__ import annotations

import json
import os
import sys
import uuid

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.session import session_factory_for_settings
from app.models.audit_event import AuditEvent
from app.models.directive import Directive
from app.models.enums import AuditEventType, DirectiveStatus, ProofObjectType, TaskLifecycleState
from app.models.memory_entry import MemoryEntry
from app.models.project import Project
from app.models.proof_object import ProofObject
from app.models.task_ledger import TaskLedger
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def _print_kv(key: str, value: object) -> None:
    print(f"{key}: {value}")


def _api_v1_base(cfg: Settings) -> str:
    host = os.environ.get("TRIDENT_PROOF_HTTP_HOST", "127.0.0.1")
    port = os.environ.get("TRIDENT_PROOF_HTTP_PORT", str(cfg.api_port))
    prefix = cfg.api_router_prefix.rstrip("/")
    return f"http://{host}:{port}{prefix}/v1"


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


def _alembic_version(session: Session) -> str | None:
    try:
        return session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    except Exception as e:  # noqa: BLE001 — proof script surfaces DB truth
        _print_kv("alembic_current_error", str(e)[:500])
        return None


def _git_head() -> str:
    if gh := os.environ.get("TRIDENT_GIT_HEAD", "").strip():
        return gh
    import subprocess

    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd="/app",
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except OSError:
        pass
    return "(unset — image build has no .git; set TRIDENT_GIT_HEAD on clawbot)"


def _ordered_audit_types(session: Session, directive_id: uuid.UUID) -> list[str]:
    rows = session.scalars(
        select(AuditEvent).where(AuditEvent.directive_id == directive_id).order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    ).all()
    return [r.event_type for r in rows]


def _find_agent_chain(types: list[str]) -> bool:
    want = (
        AuditEventType.AGENT_INVOCATION.value,
        AuditEventType.AGENT_DECISION.value,
        AuditEventType.AGENT_MCP_REQUEST.value,
        AuditEventType.MCP_EXECUTION_REQUESTED.value,
        AuditEventType.MCP_EXECUTION_COMPLETED.value,
        AuditEventType.MEMORY_WRITE.value,
        AuditEventType.AGENT_RESULT.value,
    )
    i = 0
    while i < len(types):
        if types[i] != want[0]:
            i += 1
            continue
        ok = True
        for j, w in enumerate(want):
            if i + j >= len(types) or types[i + j] != w:
                ok = False
                break
        if ok:
            return True
        i += 1
    return False


def _agent_memory_row(session: Session, directive_id: uuid.UUID) -> MemoryEntry | None:
    return session.scalar(
        select(MemoryEntry)
        .where(MemoryEntry.directive_id == directive_id)
        .where(MemoryEntry.title.isnot(None))
        .where(MemoryEntry.title.startswith("agent:engineer"))
        .order_by(MemoryEntry.created_at.asc())
        .limit(1)
    )


def _mcp_proof_for_directive(session: Session, directive_id: uuid.UUID) -> ProofObject | None:
    """Latest EXECUTION_LOG proof for this directive after workflow (agent MCP path)."""
    return session.scalar(
        select(ProofObject)
        .where(ProofObject.directive_id == directive_id)
        .where(ProofObject.proof_type == ProofObjectType.EXECUTION_LOG.value)
        .order_by(ProofObject.created_at.desc())
        .limit(1)
    )


def _validate_db(session: Session, directive_id: uuid.UUID) -> tuple[bool, str]:
    types = _ordered_audit_types(session, directive_id)
    if not _find_agent_chain(types):
        return False, "audit_chain_missing_required_subsequence"

    mem = _agent_memory_row(session, directive_id)
    if mem is None:
        return False, "agent_engineer_memory_row_missing"

    proof = _mcp_proof_for_directive(session, directive_id)
    if proof is None:
        return False, "mcp_execution_log_proof_missing"

    d = session.get(Directive, directive_id)
    ledger = session.scalar(select(TaskLedger).where(TaskLedger.directive_id == directive_id))
    if d is None or ledger is None:
        return False, "directive_or_ledger_missing"
    if ledger.current_state != TaskLifecycleState.CLOSED.value:
        return False, f"ledger_not_closed:{ledger.current_state}"
    if d.status != DirectiveStatus.COMPLETE.value:
        return False, f"directive_not_complete:{d.status}"

    return True, "ok"


def main() -> int:
    _print_kv("Directive", "100H_FINAL")

    cfg = Settings()
    SessionLocal = session_factory_for_settings(cfg)

    _print_kv("Git_HEAD", _git_head())

    verify_id_raw = os.environ.get("TRIDENT_100H_VERIFY_DIRECTIVE_ID", "").strip()
    verify_only = bool(verify_id_raw)

    with SessionLocal() as session:
        av = _alembic_version(session)
        _print_kv("Alembic_current", av or "UNKNOWN")

        if verify_only:
            try:
                did = uuid.UUID(verify_id_raw)
            except ValueError:
                _print_kv("Status", "FAIL")
                _print_kv("Known_gaps", "invalid TRIDENT_100H_VERIFY_DIRECTIVE_ID")
                return 1
            ok, reason = _validate_db(session, did)
            _print_kv("Restart_persistence_verify", "mode_TRIDENT_100H_VERIFY_DIRECTIVE_ID")
            _print_kv("Directive_ID", str(did))
            _print_kv("Audit_chain_proof", "PASS" if ok else f"FAIL:{reason}")
            types = _ordered_audit_types(session, did)
            _print_kv("Audit_event_types_count", len(types))
            mem = _agent_memory_row(session, did)
            if mem:
                _print_kv("Memory_write_proof", f"title={mem.title} vector_state={mem.vector_state}")
            _print_kv("Status", "PASS" if ok else "FAIL")
            return 0 if ok else 2

        uid, wsid, pid = _ensure_seed(session)
        body = CreateDirectiveRequest(
            workspace_id=wsid,
            project_id=pid,
            title="100H clawbot proof — engineer agent phase",
            graph_id="100h-clawbot",
            created_by_user_id=uid,
        )
        d, ledger, _gs = DirectiveRepository(session).create_directive_and_initialize(body)
        session.commit()
        did = d.id

    base = _api_v1_base(cfg)
    url = f"{base}/directives/{did}/workflow/run?reviewer_rejections_remaining=0"

    with httpx.Client(timeout=120.0) as client:
        r = client.post(url)
        _print_kv("workflow_http_status", r.status_code)
        try:
            wf_body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text}
        except json.JSONDecodeError:
            wf_body = {"raw": r.text}
        _print_kv("Workflow_run_output", json.dumps(wf_body, default=str)[:4000])

    if r.status_code != 200:
        _print_kv("Status", "FAIL")
        _print_kv("Known_gaps", "workflow_run_non_200")
        return 3

    with SessionLocal() as session:
        ok, reason = _validate_db(session, did)
        types = _ordered_audit_types(session, did)
        _print_kv("Audit_chain_ordered_event_count", len(types))
        _print_kv("Audit_chain_proof", "PASS" if ok else f"FAIL:{reason}")

        mem = _agent_memory_row(session, did)
        if mem:
            _print_kv(
                "Memory_write_proof",
                f"id={mem.id} title={mem.title} vector_state={mem.vector_state} chroma_document_id={mem.chroma_document_id}",
            )
            _print_kv(
                "Vector_path_note",
                "structured_row_authoritative; VECTOR_INDEXED preferred when Chroma healthy; VECTOR_FAILED acceptable if sidecar down",
            )
        else:
            _print_kv("Memory_write_proof", "FAIL:missing agent:engineer row")

        proof = _mcp_proof_for_directive(session, did)
        if proof:
            _print_kv("MCP_receipt_proof_object_id", str(proof.id))
            try:
                receipt = json.loads(proof.proof_summary or "{}")
                _print_kv("MCP_receipt_status", receipt.get("status", ""))
            except json.JSONDecodeError:
                _print_kv("MCP_receipt_status", "parse_error")

        inv_n = session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.directive_id == did,
                AuditEvent.event_type == AuditEventType.AGENT_INVOCATION.value,
            )
        )
        _print_kv("Agent_invocation_proof", f"AGENT_INVOCATION_count={int(inv_n or 0)}")

        d = session.get(Directive, did)
        ledger = session.scalar(select(TaskLedger).where(TaskLedger.directive_id == did))
        if d and ledger:
            _print_kv("Directive_final_status", d.status)
            _print_kv("Ledger_final_state", ledger.current_state)

    _print_kv("TRIDENT_100H_VERIFY_DIRECTIVE_ID", str(did))
    _print_kv(
        "Restart_persistence",
        "After `docker compose restart trident-api`, re-run this script with env TRIDENT_100H_VERIFY_DIRECTIVE_ID set (see above).",
    )
    _print_kv("docker_compose_ps", "(run on clawbot host: docker compose ps)")
    _print_kv("Known_gaps", "compose_ps_and_git_HEAD_from_host_when_image_has_no_.git")

    if ok:
        _print_kv("Status", "PASS")
        _print_kv("100h_clawbot_proof_ok", "1")
        return 0

    _print_kv("Status", "FAIL")
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
