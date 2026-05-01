from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import AgentRole, AuditActorType, AuditEventType, TaskLifecycleState
from app.models.graph_state import GraphState
from app.models.project import Project
from app.models.task_ledger import TaskLedger
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.audit_repository import AuditRepository
from app.schemas.directive import CreateDirectiveRequest


class DirectiveRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditRepository(session)

    def get_by_id(self, directive_id: uuid.UUID) -> Directive | None:
        return self._session.get(Directive, directive_id)

    def list_summaries(self, *, limit: int = 100) -> list[Directive]:
        q = select(Directive).order_by(Directive.created_at.desc()).limit(limit)
        return list(self._session.scalars(q).all())

    def list_summaries_for_projects(self, project_ids: list[uuid.UUID], *, limit: int = 100) -> list[Directive]:
        if not project_ids:
            return []
        q = (
            select(Directive)
            .where(Directive.project_id.in_(project_ids))
            .order_by(Directive.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(q).all())

    def create_directive_and_initialize(self, body: CreateDirectiveRequest) -> tuple[Directive, TaskLedger, GraphState]:
        ws = self._session.get(Workspace, body.workspace_id)
        if ws is None:
            raise ValueError("workspace_not_found")
        proj = self._session.get(Project, body.project_id)
        if proj is None:
            raise ValueError("project_not_found")
        if proj.workspace_id != body.workspace_id:
            raise ValueError("project_not_in_workspace")
        user = self._session.get(User, body.created_by_user_id)
        if user is None:
            raise ValueError("user_not_found")

        status_val = body.status.value
        directive = Directive(
            workspace_id=body.workspace_id,
            project_id=body.project_id,
            title=body.title,
            status=status_val,
            graph_id=body.graph_id,
            created_by_user_id=body.created_by_user_id,
        )
        self._session.add(directive)
        self._session.flush()

        gid = body.graph_id or f"graph-{directive.id}"
        now = datetime.now(timezone.utc)
        ledger = TaskLedger(
            directive_id=directive.id,
            current_state=TaskLifecycleState.DRAFT.value,
            current_agent_role=AgentRole.SYSTEM.value,
            current_owner_user_id=body.created_by_user_id,
            last_transition_at=now,
        )
        self._session.add(ledger)

        graph_state = GraphState(
            directive_id=directive.id,
            graph_id=gid,
            current_node="_placeholder",
            state_payload_json={"placeholder": True, "note": "LangGraph execution disabled (100B)"},
        )
        self._session.add(graph_state)
        self._session.flush()

        actor_id_str = str(body.created_by_user_id)
        self._audit.record(
            event_type=AuditEventType.DIRECTIVE_CREATED,
            event_payload={"title": body.title, "status": status_val, "directive_id": str(directive.id)},
            actor_type=AuditActorType.USER,
            actor_id=actor_id_str,
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )
        self._audit.record(
            event_type=AuditEventType.STATE_TRANSITION,
            event_payload={
                "context": "task_ledger_initialized",
                "to_state": TaskLifecycleState.DRAFT.value,
                "directive_id": str(directive.id),
            },
            actor_type=AuditActorType.SYSTEM,
            actor_id="task-ledger-bootstrap",
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )
        self._audit.record(
            event_type=AuditEventType.GRAPH_STATE_WRITTEN,
            event_payload={"graph_id": gid, "placeholder": True, "directive_id": str(directive.id)},
            actor_type=AuditActorType.SYSTEM,
            actor_id="graph-state-bootstrap",
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )

        return directive, ledger, graph_state
