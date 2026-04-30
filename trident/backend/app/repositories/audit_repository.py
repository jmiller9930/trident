from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.enums import AuditActorType, AuditEventType


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        event_type: AuditEventType,
        event_payload: dict[str, Any],
        actor_type: AuditActorType,
        actor_id: str | None,
        workspace_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        directive_id: uuid.UUID | None = None,
    ) -> AuditEvent:
        row = AuditEvent(
            event_type=event_type.value,
            event_payload_json=event_payload,
            actor_type=actor_type.value,
            actor_id=actor_id,
            workspace_id=workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )
        self._session.add(row)
        return row
