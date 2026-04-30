#!/usr/bin/env python3
"""100I clawbot proof: subsystem Router → LangGraph workflow/run → Agent → MCP → Memory → Audit → Proof → final state.

Validates governed chain on Postgres (+ optional Chroma). Restart persistence via verify env.

Host bootstrap (clawbot):
  docker compose exec trident-api python -m alembic upgrade head
  export TRIDENT_GIT_HEAD=$(git rev-parse HEAD)   # from repo root on host
  docker compose exec -e TRIDENT_GIT_HEAD="$TRIDENT_GIT_HEAD" trident-api python clawbot_100i_proof.py

Post-restart:
  docker compose restart trident-api
  docker compose exec trident-api env TRIDENT_100I_VERIFY_DIRECTIVE_ID=<uuid> python clawbot_100i_proof.py

Env:
  TRIDENT_PROOF_HTTP_HOST / TRIDENT_PROOF_HTTP_PORT — API from container (default 127.0.0.1:8000).
  TRIDENT_GIT_HEAD — optional (image often has no .git).
  TRIDENT_100I_VERIFY_DIRECTIVE_ID — DB-only verify (same directive after restart).

Behind reverse proxy (e.g. /trident/api): set TRIDENT_BASE_PATH=/trident on API so Settings().api_router_prefix matches mounted routes.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db.session import session_factory_for_settings
from app.memory.constants import MemoryVectorState
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

# Ordered subsequence required for 100I (interleaved audits allowed).
_AUDIT_SUBSEQUENCE_100I: tuple[str, ...] = (
    AuditEventType.ROUTER_DECISION_MADE.value,
    AuditEventType.AGENT_INVOCATION.value,
    AuditEventType.AGENT_DECISION.value,
    AuditEventType.AGENT_MCP_REQUEST.value,
    AuditEventType.MCP_EXECUTION_REQUESTED.value,
    AuditEventType.MCP_EXECUTION_COMPLETED.value,
    AuditEventType.MEMORY_WRITE.value,
    AuditEventType.AGENT_RESULT.value,
)

_GIT_AUDIT_TYPES = frozenset(
    {
        AuditEventType.GIT_STATUS_CHECKED.value,
        AuditEventType.DIFF_GENERATED.value,
    }
)


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
    except Exception as e:  # noqa: BLE001
        _print_kv("alembic_current_error", str(e)[:500])
        return None


def _git_head() -> str:
    if gh := os.environ.get("TRIDENT_GIT_HEAD", "").strip():
        return gh
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
        select(AuditEvent)
        .where(AuditEvent.directive_id == directive_id)
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    ).all()
    return [r.event_type for r in rows]


def find_100i_audit_ordered_subsequence(types: list[str]) -> bool:
    """Required ROUTER→AGENT→MCP→MEMORY→RESULT types appear in order; other audits may interleave."""
    j = 0
    want = _AUDIT_SUBSEQUENCE_100I
    for t in types:
        if j < len(want) and t == want[j]:
            j += 1
    return j == len(want)


def _every_mcp_completed_follows_agent_mcp_request(types: list[str]) -> tuple[bool, str]:
    agent_req = AuditEventType.AGENT_MCP_REQUEST.value
    mcp_done = AuditEventType.MCP_EXECUTION_COMPLETED.value
    last_complete_idx = -1
    for i, t in enumerate(types):
        if t != mcp_done:
            continue
        window = types[last_complete_idx + 1 : i]
        if agent_req not in window:
            return False, f"mcp_completed_without_agent_mcp_request_window@idx_{i}"
        last_complete_idx = i
    return True, "ok"


def _agent_engineer_memory_row(session: Session, directive_id: uuid.UUID) -> MemoryEntry | None:
    return session.scalar(
        select(MemoryEntry)
        .where(MemoryEntry.directive_id == directive_id)
        .where(MemoryEntry.title.isnot(None))
        .where(MemoryEntry.title.startswith("agent:engineer"))
        .order_by(MemoryEntry.created_at.asc())
        .limit(1)
    )


def _memory_entries_ordered(session: Session, directive_id: uuid.UUID) -> list[MemoryEntry]:
    return list(
        session.scalars(
            select(MemoryEntry)
            .where(MemoryEntry.directive_id == directive_id)
            .order_by(MemoryEntry.memory_sequence.asc(), MemoryEntry.created_at.asc())
        ).all()
    )


def _execution_log_proof(session: Session, directive_id: uuid.UUID) -> ProofObject | None:
    return session.scalar(
        select(ProofObject)
        .where(ProofObject.directive_id == directive_id)
        .where(ProofObject.proof_type == ProofObjectType.EXECUTION_LOG.value)
        .order_by(ProofObject.created_at.desc())
        .limit(1)
    )


def _proof_object_summary(session: Session, directive_id: uuid.UUID) -> tuple[int, list[str]]:
    rows = list(session.scalars(select(ProofObject).where(ProofObject.directive_id == directive_id)).all())
    types = [r.proof_type for r in rows]
    return len(rows), types


def _vector_state_valid(vs: str) -> bool:
    return vs in MemoryVectorState._value2member_map_  # type: ignore[attr-defined]


def _git_audit_count(types: list[str]) -> int:
    return sum(1 for t in types if t in _GIT_AUDIT_TYPES)


def _router_payload_ok(body: dict) -> bool:
    """Router returns decision JSON only — no execution artifacts."""
    if not isinstance(body, dict):
        return False
    allowed = {"route", "reason", "next_action", "validated"}
    return set(body.keys()) <= allowed


def validate_100i_chain(session: Session, directive_id: uuid.UUID) -> tuple[bool, str, dict]:
    """Returns (ok, reason, detail_flags)."""
    detail: dict = {}
    types = _ordered_audit_types(session, directive_id)
    detail["audit_event_count"] = len(types)
    inv_n = session.scalar(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.directive_id == directive_id,
            AuditEvent.event_type == AuditEventType.AGENT_INVOCATION.value,
        )
    )
    detail["agent_invocation_count"] = int(inv_n or 0)

    if not find_100i_audit_ordered_subsequence(types):
        return False, "audit_chain_missing_required_ordered_subsequence", detail

    bypass_ok, bypass_reason = _every_mcp_completed_follows_agent_mcp_request(types)
    detail["mcp_bypass_ok"] = bypass_ok
    if not bypass_ok:
        return False, bypass_reason, detail

    if detail["agent_invocation_count"] < 1:
        return False, "agent_invocation_missing", detail

    mem = _agent_engineer_memory_row(session, directive_id)
    if mem is None:
        return False, "agent_engineer_memory_row_missing", detail
    detail["memory_title"] = mem.title
    detail["memory_sequence"] = mem.memory_sequence
    detail["vector_state"] = mem.vector_state
    if not _vector_state_valid(mem.vector_state):
        return False, f"invalid_vector_state:{mem.vector_state}", detail

    entries = _memory_entries_ordered(session, directive_id)
    detail["memory_row_count"] = len(entries)
    if len(entries) < 1:
        return False, "memory_sequence_rows_missing", detail

    proof = _execution_log_proof(session, directive_id)
    if proof is None:
        return False, "mcp_execution_log_proof_missing", detail
    detail["execution_log_proof_id"] = str(proof.id)

    n_proof, proof_types = _proof_object_summary(session, directive_id)
    detail["proof_object_count"] = n_proof
    detail["proof_object_types"] = proof_types

    d = session.get(Directive, directive_id)
    ledger = session.scalar(select(TaskLedger).where(TaskLedger.directive_id == directive_id))
    if d is None or ledger is None:
        return False, "directive_or_ledger_missing", detail
    if ledger.current_state != TaskLifecycleState.CLOSED.value:
        return False, f"ledger_not_closed:{ledger.current_state}", detail
    if d.status != DirectiveStatus.COMPLETE.value:
        return False, f"directive_not_complete:{d.status}", detail

    git_n = _git_audit_count(types)
    detail["file_git_audit_events"] = git_n
    if git_n > 0:
        return False, f"unexpected_git_or_diff_audits:{git_n}", detail

    return True, "ok", detail


def _print_return_block(
    *,
    status: str,
    routing_proof: str,
    workflow_proof: str,
    agent_proof: str,
    mcp_proof: str,
    memory_proof: str,
    audit_proof: str,
    proof_objects: str,
    final_state: str,
    restart_persistence: str,
    bypass_violations: str,
    commit_hint: str,
) -> None:
    print("")
    print("--- Return template ---")
    _print_kv("Directive", "100I")
    _print_kv("Status", status)
    _print_kv("Commit", commit_hint)
    _print_kv("Routing proof", routing_proof)
    _print_kv("Workflow execution proof", workflow_proof)
    _print_kv("Agent execution proof", agent_proof)
    _print_kv("MCP proof", mcp_proof)
    _print_kv("Memory proof", memory_proof)
    _print_kv("Audit chain proof", audit_proof)
    _print_kv("Proof objects", proof_objects)
    _print_kv("Final state", final_state)
    _print_kv("Restart persistence", restart_persistence)
    _print_kv("Bypass violations", bypass_violations)
    _print_kv("docker compose ps", "(run on clawbot host: docker compose ps)")
    _print_kv("Known gaps", "compose_ps_and_git_HEAD_from_host_when_image_has_no_.git")


def main() -> int:
    cfg = Settings()
    SessionLocal = session_factory_for_settings(cfg)

    verify_id_raw = os.environ.get("TRIDENT_100I_VERIFY_DIRECTIVE_ID", "").strip()
    verify_only = bool(verify_id_raw)

    _print_kv("Directive", "100I")
    _print_kv("Git_HEAD", _git_head())

    routing_proof = "UNKNOWN"
    workflow_proof = "UNKNOWN"
    agent_proof = "UNKNOWN"
    mcp_proof = "UNKNOWN"
    memory_proof = "UNKNOWN"
    audit_proof = "UNKNOWN"
    proof_objects = "UNKNOWN"
    final_state = "UNKNOWN"
    bypass_violations = "UNKNOWN"
    restart_persistence = "N/A"
    commit_hint = "(set TRIDENT_GIT_HEAD from host or paste merge SHA)"
    status = "FAIL"

    with SessionLocal() as session:
        av = _alembic_version(session)
        _print_kv("Alembic_current", av or "UNKNOWN")

        if verify_only:
            try:
                did = uuid.UUID(verify_id_raw)
            except ValueError:
                _print_kv("Status", "FAIL")
                _print_kv("Known_gaps", "invalid TRIDENT_100I_VERIFY_DIRECTIVE_ID")
                _print_return_block(
                    status="FAIL",
                    routing_proof="FAIL:invalid directive id",
                    workflow_proof="N/A",
                    agent_proof="N/A",
                    mcp_proof="N/A",
                    memory_proof="N/A",
                    audit_proof="N/A",
                    proof_objects="N/A",
                    final_state="N/A",
                    restart_persistence="N/A",
                    bypass_violations="N/A",
                    commit_hint=commit_hint,
                )
                return 1

            types = _ordered_audit_types(session, did)
            router_ok = AuditEventType.ROUTER_DECISION_MADE.value in types
            seq_ok = find_100i_audit_ordered_subsequence(types)
            bypass_ok, bypass_reason = _every_mcp_completed_follows_agent_mcp_request(types)

            ok, reason, detail = validate_100i_chain(session, did)

            _print_kv("Restart_persistence_verify", "mode_TRIDENT_100I_VERIFY_DIRECTIVE_ID")
            _print_kv("Directive_ID", str(did))
            _print_kv("ROUTER_DECISION_MADE_present", str(router_ok))
            _print_kv("Audit_subsequence_proof", "PASS" if seq_ok else "FAIL")
            _print_kv("MCP_no_bypass_guard", "PASS" if bypass_ok else f"FAIL:{bypass_reason}")
            _print_kv("Audit_event_types_count", len(types))
            _print_kv("Chain_validation", "PASS" if ok else f"FAIL:{reason}")

            mem = _agent_engineer_memory_row(session, did)
            if mem:
                _print_kv(
                    "Memory_write_proof",
                    f"title={mem.title} memory_sequence={mem.memory_sequence} vector_state={mem.vector_state}",
                )
            proof_v = _execution_log_proof(session, did)
            if proof_v:
                _print_kv("EXECUTION_LOG", str(proof_v.id))

            routing_proof = "PASS (ROUTER_DECISION_MADE in audit trail)" if router_ok else "FAIL:missing ROUTER_DECISION_MADE"
            workflow_proof = "PASS (DB — directive COMPLETE, ledger CLOSED)" if ok else f"FAIL:{reason}"
            agent_proof = f"PASS (AGENT_INVOCATION_count={detail.get('agent_invocation_count', 0)})"
            if detail.get("agent_invocation_count", 0) < 1:
                agent_proof = "FAIL:no AGENT_INVOCATION"

            mcp_proof = (
                "PASS (EXECUTION_LOG + MCP bypass guard)"
                if proof_v and bypass_ok
                else (f"FAIL:{bypass_reason}" if not bypass_ok else "FAIL:missing EXECUTION_LOG proof")
            )

            memory_proof = "FAIL"
            if ok:
                memory_proof = (
                    f"PASS (rows={detail['memory_row_count']}, engineer_sequence={detail['memory_sequence']}, "
                    f"vector_state={detail['vector_state']})"
                )
            elif mem:
                memory_proof = f"PARTIAL (engineer row present but chain FAIL:{reason})"

            audit_proof = "PASS" if seq_ok and ok else ("FAIL:audit_subsequence" if not seq_ok else f"FAIL:{reason}")
            proof_objects = (
                f"PASS (count={detail.get('proof_object_count', 0)}, types={detail.get('proof_object_types', [])})"
                if ok
                else "FAIL"
            )
            final_state = "PASS" if ok else f"FAIL:{reason}"
            bypass_violations = "FAIL"
            if bypass_ok and detail.get("file_git_audit_events", -1) == 0 and detail.get("agent_invocation_count", 0) >= 1:
                bypass_violations = "PASS (MCP guard + no GIT/DIFF audits + agent invocation)"
            elif not bypass_ok:
                bypass_violations = f"FAIL:{bypass_reason}"
            elif detail.get("file_git_audit_events", 0) > 0:
                bypass_violations = "FAIL:unexpected GIT/DIFF audits during proof run"

            restart_persistence = "PASS" if ok else "FAIL"
            status = "PASS" if ok else "FAIL"

            _print_kv("Status", status)
            if ok:
                _print_kv("restart_verify_PASS", "1")

            _print_return_block(
                status=status,
                routing_proof=routing_proof,
                workflow_proof=workflow_proof,
                agent_proof=agent_proof,
                mcp_proof=mcp_proof,
                memory_proof=memory_proof,
                audit_proof=audit_proof,
                proof_objects=proof_objects,
                final_state=final_state,
                restart_persistence=restart_persistence,
                bypass_violations=bypass_violations,
                commit_hint=commit_hint,
            )
            _print_kv("100i_clawbot_proof_verify_ok", "1" if ok else "0")
            return 0 if ok else 2

        uid, wsid, pid = _ensure_seed(session)
        body = CreateDirectiveRequest(
            workspace_id=wsid,
            project_id=pid,
            title="100I clawbot proof — end-to-end governed chain",
            graph_id="100i-clawbot",
            created_by_user_id=uid,
        )
        d, ledger, _gs = DirectiveRepository(session).create_directive_and_initialize(body)
        session.commit()
        did = d.id
        tid = ledger.id

    base = _api_v1_base(cfg)
    router_body = {
        "directive_id": str(did),
        "task_id": str(tid),
        "agent_role": "ENGINEER",
        "intent": "route.langgraph",
        "payload": {},
    }

    routing_http_ok = False
    routing_json: dict = {}
    with httpx.Client(timeout=60.0) as client:
        rr = client.post(f"{base}/router/route", json=router_body)
        _print_kv("routing_http_status", rr.status_code)
        try:
            routing_json = rr.json() if rr.headers.get("content-type", "").startswith("application/json") else {}
        except json.JSONDecodeError:
            routing_json = {}
        _print_kv("routing_response", json.dumps(routing_json, default=str)[:2000])
        routing_http_ok = rr.status_code == 200 and bool(routing_json.get("validated")) and routing_json.get("route") == "LANGGRAPH"
        _print_kv("routing_decision_only_payload_ok", str(_router_payload_ok(routing_json)))

    if not routing_http_ok:
        routing_proof = "FAIL:router HTTP or LANGGRAPH decision"
        _print_kv("Status", "FAIL")
        _print_kv("Known_gaps", "router_route_failed")
        _print_return_block(
            status="FAIL",
            routing_proof=routing_proof,
            workflow_proof="SKIPPED",
            agent_proof="SKIPPED",
            mcp_proof="SKIPPED",
            memory_proof="SKIPPED",
            audit_proof="SKIPPED",
            proof_objects="SKIPPED",
            final_state="SKIPPED",
            restart_persistence="SKIPPED",
            bypass_violations="SKIPPED",
            commit_hint=commit_hint,
        )
        return 5

    routing_proof = "PASS (HTTP 200, validated LANGGRAPH, ROUTER_DECISION_MADE expected in audits)"

    wf_url = f"{base}/directives/{did}/workflow/run?reviewer_rejections_remaining=0"
    with httpx.Client(timeout=120.0) as client:
        r = client.post(wf_url)
        _print_kv("workflow_http_status", r.status_code)
        try:
            wf_body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"raw": r.text}
        except json.JSONDecodeError:
            wf_body = {"raw": r.text}
        _print_kv("Workflow_run_output", json.dumps(wf_body, default=str)[:4000])

    workflow_http_ok = r.status_code == 200
    workflow_proof = "PASS" if workflow_http_ok else f"FAIL:http_{r.status_code}"

    if not workflow_http_ok:
        _print_kv("Status", "FAIL")
        _print_kv("Known_gaps", "workflow_run_non_200")
        _print_return_block(
            status="FAIL",
            routing_proof=routing_proof,
            workflow_proof=workflow_proof,
            agent_proof="SKIPPED",
            mcp_proof="SKIPPED",
            memory_proof="SKIPPED",
            audit_proof="SKIPPED",
            proof_objects="SKIPPED",
            final_state="SKIPPED",
            restart_persistence="SKIPPED",
            bypass_violations="SKIPPED",
            commit_hint=commit_hint,
        )
        return 3

    with SessionLocal() as session:
        types = _ordered_audit_types(session, did)
        router_audit_ok = AuditEventType.ROUTER_DECISION_MADE.value in types
        if not router_audit_ok:
            routing_proof = "FAIL:ROUTER_DECISION_MADE missing after router POST"

        ok, reason, detail = validate_100i_chain(session, did)
        seq_ok = find_100i_audit_ordered_subsequence(types)
        bypass_ok, bypass_reason = _every_mcp_completed_follows_agent_mcp_request(types)

        _print_kv("ROUTER_DECISION_MADE_present", str(router_audit_ok))
        _print_kv("MCP_no_bypass_guard", "PASS" if bypass_ok else f"FAIL:{bypass_reason}")
        _print_kv("Audit_chain_ordered_event_count", len(types))
        _print_kv("Audit_chain_proof", "PASS" if ok and seq_ok else f"FAIL:{reason}")

        mem = _agent_engineer_memory_row(session, did)
        if mem:
            _print_kv(
                "Memory_write_proof",
                f"id={mem.id} title={mem.title} memory_sequence={mem.memory_sequence} "
                f"vector_state={mem.vector_state} chroma_document_id={mem.chroma_document_id}",
            )
            _print_kv(
                "Vector_path_note",
                "structured_row_authoritative; VECTOR_INDEXED preferred when Chroma healthy; VECTOR_FAILED acceptable if sidecar down",
            )
        else:
            _print_kv("Memory_write_proof", "FAIL:missing agent:engineer row")

        proof = _execution_log_proof(session, did)
        if proof:
            _print_kv("EXECUTION_LOG", str(proof.id))
            _print_kv("MCP_receipt_proof_object_id", str(proof.id))
            try:
                receipt = json.loads(proof.proof_summary or "{}")
                _print_kv("MCP_receipt_status", receipt.get("status", ""))
            except json.JSONDecodeError:
                _print_kv("MCP_receipt_status", "parse_error")

        inv_n = detail.get("agent_invocation_count", 0)
        _print_kv("Agent_invocation_proof", f"AGENT_INVOCATION_count={inv_n}")

        drow = session.get(Directive, did)
        led = session.scalar(select(TaskLedger).where(TaskLedger.directive_id == did))
        if drow and led:
            _print_kv("Directive_final_status", drow.status)
            _print_kv("Ledger_final_state", led.current_state)

        n_proof, p_types = _proof_object_summary(session, did)
        _print_kv("Proof_objects_count", n_proof)
        _print_kv("Proof_objects_types", json.dumps(p_types))

        git_n = _git_audit_count(types)
        _print_kv("file_git_audit_events", git_n)

        audit_proof = "PASS" if ok and seq_ok and router_audit_ok else f"FAIL:{reason}"
        agent_proof = f"PASS (AGENT_INVOCATION_count={inv_n})" if inv_n >= 1 else "FAIL:no agent invocation"
        mcp_proof = "PASS (EXECUTION_LOG + MCP bypass guard)" if proof and bypass_ok and ok else f"FAIL:{reason}"
        memory_proof = (
            f"PASS (memory_sequence={detail.get('memory_row_count', 0)} rows, engineer vector ok)"
            if ok and mem
            else f"FAIL:{reason}"
        )
        proof_objects = f"PASS (n={n_proof}, types={p_types})" if ok else "FAIL"
        final_state = "PASS (COMPLETE / CLOSED)" if ok else f"FAIL:{reason}"
        bypass_violations = (
            "PASS"
            if bypass_ok and git_n == 0 and inv_n >= 1
            else f"FAIL bypass_ok={bypass_ok} git={git_n} inv={inv_n}"
        )

        if router_audit_ok and routing_http_ok:
            routing_proof = "PASS (HTTP LANGGRAPH + ROUTER_DECISION_MADE audit)"

        restart_persistence = (
            "After `docker compose restart trident-api`, re-run with env TRIDENT_100I_VERIFY_DIRECTIVE_ID "
            f"(directive_id={did})."
        )

        status = "PASS" if ok and router_audit_ok else "FAIL"

        _print_kv("TRIDENT_100I_VERIFY_DIRECTIVE_ID", str(did))
        _print_kv("Restart_persistence", restart_persistence)

        _print_return_block(
            status=status,
            routing_proof=routing_proof,
            workflow_proof=workflow_proof,
            agent_proof=agent_proof,
            mcp_proof=mcp_proof,
            memory_proof=memory_proof,
            audit_proof=audit_proof,
            proof_objects=proof_objects,
            final_state=final_state,
            restart_persistence="PENDING_RESTART_RUN",
            bypass_violations=bypass_violations,
            commit_hint=commit_hint,
        )

        if ok and router_audit_ok:
            _print_kv("Status", "PASS")
            _print_kv("100i_clawbot_proof_ok", "1")
            return 0

        _print_kv("Status", "FAIL")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
