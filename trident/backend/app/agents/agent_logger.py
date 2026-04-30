"""Agent-layer audits — distinct from MCPService router/MCP receipts."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import AgentRole, AuditActorType, AuditEventType
from app.models.task_ledger import TaskLedger
from app.repositories.audit_repository import AuditRepository


class AgentAuditLogger:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditRepository(session)

    def invocation(
        self,
        *,
        directive: Directive,
        ledger: TaskLedger,
        node_name: str,
        role: AgentRole,
    ) -> None:
        self._audit.record(
            event_type=AuditEventType.AGENT_INVOCATION,
            event_payload={
                "node": node_name,
                "agent_role": role.value,
                "task_id": str(ledger.id),
            },
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{role.value}",
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )

    def decision(self, *, directive: Directive, ledger: TaskLedger, node_name: str, payload: dict[str, Any]) -> None:
        self._audit.record(
            event_type=AuditEventType.AGENT_DECISION,
            event_payload={"node": node_name, "task_id": str(ledger.id), **payload},
            actor_type=AuditActorType.AGENT,
            actor_id="agent:decision",
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )

    def mcp_request(
        self,
        *,
        directive: Directive,
        ledger: TaskLedger,
        node_name: str,
        command: str,
        target: str,
        explicitly_approved: bool,
    ) -> None:
        self._audit.record(
            event_type=AuditEventType.AGENT_MCP_REQUEST,
            event_payload={
                "node": node_name,
                "task_id": str(ledger.id),
                "command": command[:500],
                "target": target,
                "explicitly_approved": explicitly_approved,
            },
            actor_type=AuditActorType.AGENT,
            actor_id="agent:mcp_request",
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )

    def result(self, *, directive: Directive, ledger: TaskLedger, node_name: str, payload: dict[str, Any]) -> None:
        self._audit.record(
            event_type=AuditEventType.AGENT_RESULT,
            event_payload={"node": node_name, "task_id": str(ledger.id), **payload},
            actor_type=AuditActorType.AGENT,
            actor_id="agent:result",
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )
