"""Structured MCP audit lines (100F) — uses AuditRepository; failures visible in event_type + payload."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType
from app.repositories.audit_repository import AuditRepository


class MCPAuditLogger:
    def __init__(self, session: Session) -> None:
        self._audit = AuditRepository(session)

    def execution_requested(
        self,
        directive: Directive,
        *,
        task_id: uuid.UUID,
        agent_role: str,
        command: str,
        target: str,
        risk: str,
        rationale: str,
    ) -> None:
        self._audit.record(
            event_type=AuditEventType.MCP_EXECUTION_REQUESTED,
            event_payload={
                "task_id": str(task_id),
                "agent_role": agent_role,
                "command_preview": command[:500],
                "target": target,
                "risk": risk,
                "classification_rationale": rationale,
            },
            actor_type=AuditActorType.AGENT,
            actor_id=agent_role,
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )

    def execution_completed(
        self,
        directive: Directive,
        *,
        task_id: uuid.UUID,
        agent_role: str,
        proof_object_id: uuid.UUID,
        receipt_summary: dict[str, Any],
    ) -> None:
        self._audit.record(
            event_type=AuditEventType.MCP_EXECUTION_COMPLETED,
            event_payload={
                "task_id": str(task_id),
                "agent_role": agent_role,
                "proof_object_id": str(proof_object_id),
                "receipt": receipt_summary,
            },
            actor_type=AuditActorType.AGENT,
            actor_id=agent_role,
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )

    def execution_rejected(
        self,
        directive: Directive,
        *,
        task_id: uuid.UUID,
        agent_role: str,
        reason_code: str,
        detail: dict[str, Any],
        proof_object_id: uuid.UUID | None = None,
    ) -> None:
        payload = {
            "task_id": str(task_id),
            "agent_role": agent_role,
            "reason_code": reason_code,
            **detail,
        }
        if proof_object_id is not None:
            payload["proof_object_id"] = str(proof_object_id)
        self._audit.record(
            event_type=AuditEventType.MCP_EXECUTION_REJECTED,
            event_payload=payload,
            actor_type=AuditActorType.AGENT,
            actor_id=agent_role,
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )

    def execution_failed(
        self,
        directive: Directive,
        *,
        task_id: uuid.UUID,
        agent_role: str,
        reason_code: str,
        detail: dict[str, Any],
    ) -> None:
        self._audit.record(
            event_type=AuditEventType.MCP_EXECUTION_FAILED,
            event_payload={
                "task_id": str(task_id),
                "agent_role": agent_role,
                "reason_code": reason_code,
                **detail,
            },
            actor_type=AuditActorType.AGENT,
            actor_id=agent_role,
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )
