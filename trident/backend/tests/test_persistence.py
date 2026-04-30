"""Persistence smoke tests — directive 100B §12.2."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models import AuditEvent, Directive, GraphState, TaskLedger
from app.models.enums import DirectiveStatus
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


def test_directive_task_graph_audit_persist(sqlite_engine, db_session, minimal_project_ids) -> None:
    ids = minimal_project_ids
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Persist me",
        graph_id="g-1",
        created_by_user_id=ids["user_id"],
        status=DirectiveStatus.DRAFT,
    )
    repo = DirectiveRepository(db_session)
    d, ledger, gs = repo.create_directive_and_initialize(body)
    db_session.commit()

    d2 = db_session.get(Directive, d.id)
    assert d2 is not None
    assert d2.title == "Persist me"

    tl = db_session.scalar(select(TaskLedger).where(TaskLedger.directive_id == d.id))
    assert tl is not None
    assert tl.current_state == "DRAFT"

    g2 = db_session.scalar(select(GraphState).where(GraphState.directive_id == d.id))
    assert g2 is not None
    assert g2.state_payload_json.get("placeholder") is True

    audits = db_session.scalars(select(AuditEvent).where(AuditEvent.directive_id == d.id)).all()
    assert len(audits) >= 3
