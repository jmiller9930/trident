"""Audit routing decisions (100G) — ROUTER_DECISION_MADE only."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType
from app.repositories.audit_repository import AuditRepository


class RouterAuditLogger:
    def __init__(self, session: Session) -> None:
        self._audit = AuditRepository(session)

    def decision_made(
        self,
        directive: Directive,
        *,
        task_id: uuid.UUID,
        agent_role: str,
        intent_preview: str,
        payload_keys: list[str],
        decision_payload: dict[str, Any],
    ) -> None:
        self._audit.record(
            event_type=AuditEventType.ROUTER_DECISION_MADE,
            event_payload={
                "task_id": str(task_id),
                "agent_role": agent_role,
                "intent_preview": intent_preview[:500],
                "payload_keys": payload_keys,
                **decision_payload,
            },
            actor_type=AuditActorType.AGENT,
            actor_id=agent_role,
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )
