"""IDE_002 — service logic for status + proof-summary polling endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.proof_object import ProofObject
from app.repositories.directive_repository import DirectiveRepository
from app.repositories.task_ledger_repository import TaskLedgerRepository
from app.schemas.ide_status import IdeProofSummaryResponse, IdeStatusResponse

_ROUTING_EVENT = AuditEventType.MODEL_ROUTING_DECISION.value
_MCP_EVENTS = (
    AuditEventType.MCP_EXECUTION_REQUESTED.value,
    AuditEventType.MCP_EXECUTION_COMPLETED.value,
    AuditEventType.MCP_EXECUTION_REJECTED.value,
    AuditEventType.MCP_EXECUTION_FAILED.value,
)
_PATCH_EVENTS = (
    AuditEventType.PATCH_PROPOSED.value,
    AuditEventType.PATCH_APPLIED.value,
    AuditEventType.PATCH_REJECTED.value,
)


def _safe_routing_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return only the defined contract fields — no internal schema bleed."""
    return {
        "routing_outcome": payload.get("routing_outcome"),
        "escalation_trigger_code": payload.get("escalation_trigger_code"),
        "calibrated_confidence": payload.get("calibrated_confidence"),
        "local_model": payload.get("local_model"),
        "external_model": payload.get("external_model"),
        "blocked_external": payload.get("blocked_external"),
        "blocked_reason_code": payload.get("blocked_reason_code"),
    }


def _safe_mcp_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": payload.get("event_type"),
        "target": payload.get("target"),
        "command": payload.get("command"),
        "result_code": payload.get("result_code"),
    }


def _safe_patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_path": payload.get("file_path"),
        "summary": payload.get("summary"),
        "correlation_id": payload.get("correlation_id"),
    }


def _last_routing(session: Session, directive_id: uuid.UUID) -> tuple[dict[str, Any] | None, str | None]:
    row = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.directive_id == directive_id, AuditEvent.event_type == _ROUTING_EVENT)
        .order_by(desc(AuditEvent.created_at))
        .limit(1)
    ).first()
    if row is None:
        return None, None
    p = row.event_payload_json or {}
    return _safe_routing_payload(p), p.get("external_model") or p.get("local_model")


def _last_mcp_events(session: Session, directive_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.directive_id == directive_id, AuditEvent.event_type.in_(_MCP_EVENTS))
            .order_by(desc(AuditEvent.created_at))
            .limit(3)
        ).all()
    )
    return [_safe_mcp_payload(r.event_payload_json or {}) for r in rows]


def _last_patch_event(session: Session, directive_id: uuid.UUID) -> dict[str, Any] | None:
    row = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.directive_id == directive_id, AuditEvent.event_type.in_(_PATCH_EVENTS))
        .order_by(desc(AuditEvent.created_at))
        .limit(1)
    ).first()
    if row is None:
        return None
    return _safe_patch_payload(row.event_payload_json or {})


def get_ide_status(session: Session, directive_id: uuid.UUID) -> IdeStatusResponse:
    d = DirectiveRepository(session).get_by_id(directive_id)
    if d is None:
        raise ValueError("directive_not_found")
    ledger = TaskLedgerRepository(session).get_by_directive_id(directive_id)
    if ledger is None:
        raise ValueError("task_ledger_not_found")

    routing_payload, routing_model = _last_routing(session, directive_id)

    return IdeStatusResponse(
        directive_id=d.id,
        title=d.title,
        directive_status=d.status,
        ledger_state=ledger.current_state,
        current_agent_role=ledger.current_agent_role,
        last_routing_decision=routing_payload,
        last_routing_model=routing_model,
    )


def get_ide_proof_summary(session: Session, directive_id: uuid.UUID) -> IdeProofSummaryResponse:
    d = DirectiveRepository(session).get_by_id(directive_id)
    if d is None:
        raise ValueError("directive_not_found")
    ledger = TaskLedgerRepository(session).get_by_directive_id(directive_id)
    if ledger is None:
        raise ValueError("task_ledger_not_found")

    proof_count = session.scalar(
        select(func.count()).select_from(ProofObject).where(ProofObject.directive_id == directive_id)
    ) or 0

    routing_payload, routing_model = _last_routing(session, directive_id)
    mcp_events = _last_mcp_events(session, directive_id)
    patch_event = _last_patch_event(session, directive_id)

    return IdeProofSummaryResponse(
        directive_id=d.id,
        title=d.title,
        directive_status=d.status,
        ledger_state=ledger.current_state,
        current_agent_role=ledger.current_agent_role,
        proof_count=int(proof_count),
        last_routing_decision=routing_payload,
        last_routing_model=routing_model,
        last_mcp_events=mcp_events,
        last_patch_event=patch_event,
    )
