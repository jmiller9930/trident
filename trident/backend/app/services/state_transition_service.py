from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType, DirectiveStatus
from app.models.state_enums import StateTransitionActorType
from app.models.state_transition_log import StateTransitionLog
from app.repositories.audit_repository import AuditRepository


class StateTransitionService:
    """Validates directive status transitions and writes state_transition_log + audit (STATE_002 foundation)."""

    ALLOWED_DIRECTIVE: frozenset[tuple[str, str]] = frozenset(
        {(DirectiveStatus.DRAFT.value, DirectiveStatus.ISSUED.value)}
    )

    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditRepository(session)

    def transition_directive_status(
        self,
        *,
        directive_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        to_status: DirectiveStatus,
        reason: str | None = None,
        correlation_id: uuid.UUID | None = None,
    ) -> Directive:
        stmt = select(Directive).where(Directive.id == directive_id).with_for_update()
        d = self._session.scalars(stmt).one_or_none()
        if d is None:
            raise ValueError("directive_not_found")

        from_st = d.status
        key = (from_st, to_status.value)
        if key not in self.ALLOWED_DIRECTIVE:
            raise ValueError("invalid_directive_status_transition")

        d.status = to_status.value
        log = StateTransitionLog(
            directive_id=d.id,
            from_state=from_st,
            to_state=to_status.value,
            actor_type=StateTransitionActorType.USER.value,
            actor_id=actor_user_id,
            correlation_id=correlation_id,
            reason=reason,
        )
        self._session.add(log)
        self._audit.record(
            event_type=AuditEventType.STATE_TRANSITION,
            event_payload={
                "entity": "directive",
                "from_state": from_st,
                "to_state": to_status.value,
                "directive_id": str(d.id),
            },
            actor_type=AuditActorType.USER,
            actor_id=str(actor_user_id),
            workspace_id=d.workspace_id,
            project_id=d.project_id,
            directive_id=d.id,
        )
        self._audit.record(
            event_type=AuditEventType.CONTROL_PLANE_ACTION,
            event_payload={"action": "directive_issue", "directive_id": str(d.id)},
            actor_type=AuditActorType.USER,
            actor_id=str(actor_user_id),
            workspace_id=d.workspace_id,
            project_id=d.project_id,
            directive_id=d.id,
        )
        return d
