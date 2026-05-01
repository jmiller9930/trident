"""100N — single orchestrated IDE entrypoint (no agent logic duplication)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.ide.chat_service import process_ide_chat
from app.memory.memory_reader import MemoryReader
from app.models.audit_event import AuditEvent
from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType, ProofObjectType
from app.models.proof_object import ProofObject
from app.models.task_ledger import TaskLedger
from app.repositories.audit_repository import AuditRepository
from app.repositories.directive_repository import DirectiveRepository
from app.repositories.task_ledger_repository import TaskLedgerRepository
from app.router.router_validator import validate_agent_role
from app.router.router_service import RouterService
from app.schemas.ide_action import IdeActionRequest, IdeActionResponse, IdeMcpAuditSnippet, IdeRouterSnapshot
from app.schemas.router import RouterRouteRequest
from app.workflow.spine import run_spine_workflow

_MCP_EVENT_TYPES = (
    AuditEventType.MCP_EXECUTION_REQUESTED.value,
    AuditEventType.MCP_EXECUTION_COMPLETED.value,
    AuditEventType.MCP_EXECUTION_REJECTED.value,
)


def _audit_orchestrated(
    session: Session,
    *,
    correlation_id: uuid.UUID,
    action: str,
    directive: Directive,
    actor_id: str | None,
    extra: dict[str, Any],
) -> None:
    AuditRepository(session).record(
        event_type=AuditEventType.IDE_ORCHESTRATED_ACTION,
        event_payload={
            "correlation_id": str(correlation_id),
            "action": action,
            "project_id": str(directive.project_id),
            "directive_id": str(directive.id),
            **extra,
        },
        actor_type=AuditActorType.USER,
        actor_id=actor_id or "ide-client",
        workspace_id=directive.workspace_id,
        project_id=directive.project_id,
        directive_id=directive.id,
    )


def _resolve_directive_and_ledger(session: Session, *, project_id: uuid.UUID, directive_id: uuid.UUID) -> tuple[Directive, TaskLedger]:
    d = DirectiveRepository(session).get_by_id(directive_id)
    if d is None:
        raise ValueError("directive_not_found")
    if d.project_id != project_id:
        raise ValueError("directive_project_mismatch")
    ledger = TaskLedgerRepository(session).get_by_directive_id(directive_id)
    if ledger is None:
        raise ValueError("task_ledger_not_found")
    return d, ledger


def _router_snapshot(session: Session, *, directive_id: uuid.UUID, task_id: uuid.UUID, agent_role: str, intent: str) -> IdeRouterSnapshot:
    out = RouterService(session).decide(
        RouterRouteRequest(
            directive_id=directive_id,
            task_id=task_id,
            agent_role=agent_role,
            intent=intent,
            payload={},
        )
    )
    return IdeRouterSnapshot(
        route=out.route,
        reason=out.reason,
        next_action=out.next_action,
        validated=out.validated,
    )


def _memory_preview_dict(session: Session, directive_id: uuid.UUID) -> dict[str, Any]:
    data = MemoryReader(session).read_directive(directive_id, vector_query=None, vector_top_k=3)
    err = data.get("error")
    if err:
        return {"error": err}
    entries = data.get("memory_entries") or []
    return {
        "memory_entry_count": len(entries),
        "sample_entries": entries[:5],
        "task_ledger": data.get("task_ledger"),
    }


def _mcp_recent(session: Session, directive_id: uuid.UUID) -> list[IdeMcpAuditSnippet]:
    rows = list(
        session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.directive_id == directive_id,
                AuditEvent.event_type.in_(_MCP_EVENT_TYPES),
            )
            .order_by(desc(AuditEvent.created_at))
            .limit(5)
        ).all()
    )
    out: list[IdeMcpAuditSnippet] = []
    for r in rows:
        prev = json.dumps(r.event_payload_json, default=str)[:500]
        out.append(
            IdeMcpAuditSnippet(
                event_type=r.event_type,
                created_at=r.created_at.isoformat() if r.created_at else None,
                payload_preview=prev,
            )
        )
    return out


def _response_base(
    *,
    correlation_id: uuid.UUID,
    body: IdeActionRequest,
    directive: Directive,
    ledger: TaskLedger,
    router: IdeRouterSnapshot | None = None,
    memory_preview: dict[str, Any] | None = None,
    mcp_recent: list[IdeMcpAuditSnippet] | None = None,
    reply: str | None = None,
    nodes_executed: list[str] | None = None,
    proof_object_id: uuid.UUID | None = None,
    patch_guidance: str | None = None,
) -> IdeActionResponse:
    return IdeActionResponse(
        correlation_id=correlation_id,
        action=body.action,
        project_id=body.project_id,
        directive_id=body.directive_id,
        directive_status=directive.status,
        task_ledger_state=ledger.current_state,
        current_agent_role=ledger.current_agent_role,
        reply=reply,
        nodes_executed=nodes_executed,
        proof_object_id=proof_object_id,
        router=router,
        memory_preview=memory_preview,
        mcp_recent=mcp_recent,
        patch_guidance=patch_guidance,
    )


def process_ide_action(session: Session, body: IdeActionRequest) -> IdeActionResponse:
    validate_agent_role(body.agent_role)
    correlation_id = uuid.uuid4()
    directive, ledger = _resolve_directive_and_ledger(
        session,
        project_id=body.project_id,
        directive_id=body.directive_id,
    )

    if body.action == "ASK":
        assert body.prompt is not None
        intent = (body.intent_for_router or body.prompt).strip() or "ide_ask"
        router = _router_snapshot(
            session,
            directive_id=body.directive_id,
            task_id=ledger.id,
            agent_role=body.agent_role,
            intent=intent[:8192],
        )
        memory_preview = _memory_preview_dict(session, body.directive_id)
        mcp_recent = _mcp_recent(session, body.directive_id)

        reply, _cid, proof_id = process_ide_chat(
            session,
            directive_id=body.directive_id,
            prompt=body.prompt,
            actor_id=body.actor_id,
            correlation_id=correlation_id,
        )

        _audit_orchestrated(
            session,
            correlation_id=correlation_id,
            action="ASK",
            directive=directive,
            actor_id=body.actor_id,
            extra={"proof_object_id": str(proof_id), "router_validated": router.validated},
        )

        session.refresh(directive)
        session.refresh(ledger)

        return _response_base(
            correlation_id=correlation_id,
            body=body,
            directive=directive,
            ledger=ledger,
            router=router,
            memory_preview=memory_preview,
            mcp_recent=mcp_recent,
            reply=reply,
            proof_object_id=proof_id,
        )

    if body.action == "RUN_WORKFLOW":
        state = run_spine_workflow(
            session,
            body.directive_id,
            reviewer_rejections_remaining=body.reviewer_rejections_remaining,
        )
        nodes = list(state.get("nodes_executed") or [])

        session.refresh(directive)
        session.refresh(ledger)

        intent = (body.prompt or "").strip() or "workflow_progress ledger_transition"
        router = _router_snapshot(
            session,
            directive_id=body.directive_id,
            task_id=ledger.id,
            agent_role=body.agent_role,
            intent=intent[:8192],
        )

        _audit_orchestrated(
            session,
            correlation_id=correlation_id,
            action="RUN_WORKFLOW",
            directive=directive,
            actor_id=body.actor_id,
            extra={
                "nodes_executed": nodes,
                "final_ledger_state": ledger.current_state,
                "reviewer_rejections_remaining": body.reviewer_rejections_remaining,
            },
        )

        return _response_base(
            correlation_id=correlation_id,
            body=body,
            directive=directive,
            ledger=ledger,
            router=router,
            reply=f"workflow_step correlation_id={correlation_id} nodes={nodes}",
            nodes_executed=nodes,
        )

    if body.action == "PROPOSE_PATCH":
        guidance = (
            "Agent-driven edits must use the governed patch workflow (100M): acquire lock, "
            "run **Trident: Patch workflow (preview / apply)**, then POST apply-complete. "
            "Enable `trident.patchWorkflowRequired` for strict patch-only mode."
        )
        preview = (body.prompt or "").strip()
        proof_summary = json.dumps(
            {
                "schema": "ide_patch_guidance_v1",
                "correlation_id": str(correlation_id),
                "prompt_preview": preview[:2000],
            }
        )
        proof = ProofObject(
            directive_id=body.directive_id,
            proof_type=ProofObjectType.CHAT_LOG.value,
            proof_summary=proof_summary,
            proof_uri=None,
            proof_hash=None,
            created_by_agent_role=body.agent_role.strip(),
        )
        session.add(proof)
        session.flush()

        intent = preview or "mcp_execute tool_execution_path propose_change"
        router = _router_snapshot(
            session,
            directive_id=body.directive_id,
            task_id=ledger.id,
            agent_role=body.agent_role,
            intent=intent[:8192],
        )
        memory_preview = _memory_preview_dict(session, body.directive_id)
        mcp_recent = _mcp_recent(session, body.directive_id)

        _audit_orchestrated(
            session,
            correlation_id=correlation_id,
            action="PROPOSE_PATCH",
            directive=directive,
            actor_id=body.actor_id,
            extra={"proof_object_id": str(proof.id)},
        )

        session.refresh(directive)
        session.refresh(ledger)

        return _response_base(
            correlation_id=correlation_id,
            body=body,
            directive=directive,
            ledger=ledger,
            router=router,
            memory_preview=memory_preview,
            mcp_recent=mcp_recent,
            reply=guidance,
            proof_object_id=proof.id,
            patch_guidance=guidance,
        )

    raise ValueError("unsupported_action")
