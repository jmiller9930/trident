"""Audit trail — directive 100B §12.4."""

from __future__ import annotations

from sqlalchemy import select

from app.models import AuditEvent
from app.models.enums import AuditEventType, DirectiveStatus
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def test_create_directive_emits_audit_events(db_session, minimal_project_ids) -> None:
    ids = minimal_project_ids
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Audited",
        graph_id=None,
        created_by_user_id=ids["user_id"],
        status=DirectiveStatus.ACTIVE,
    )
    repo = DirectiveRepository(db_session)
    d, _l, _g = repo.create_directive_and_initialize(body)
    db_session.commit()

    rows = db_session.scalars(select(AuditEvent).where(AuditEvent.directive_id == d.id)).all()
    types = {r.event_type for r in rows}
    assert AuditEventType.DIRECTIVE_CREATED.value in types
    assert AuditEventType.STATE_TRANSITION.value in types
    assert AuditEventType.GRAPH_STATE_WRITTEN.value in types

    for r in rows:
        assert r.workspace_id == ids["workspace_id"]
        assert r.project_id == ids["project_id"]
        assert r.directive_id == d.id
        assert r.event_payload_json
