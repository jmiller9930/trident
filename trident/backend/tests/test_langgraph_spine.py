"""LangGraph spine — directive 100C."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.directive import Directive
from app.models.enums import DirectiveStatus, TaskLifecycleState
from app.models.graph_state import GraphState
from app.repositories.directive_repository import DirectiveRepository
from app.repositories.task_ledger_repository import TaskLedgerRepository
from app.schemas.directive import CreateDirectiveRequest
from app.workflow import spine as spine_mod
from app.workflow.spine import run_spine_workflow


def _create_directive(session: Session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Spine test",
        graph_id="spine-v1",
        created_by_user_id=ids["user_id"],
    )
    dr = DirectiveRepository(session)
    d, _l, _g = dr.create_directive_and_initialize(body)
    session.commit()
    return d.id


def test_spine_happy_path_executes_full_sequence(db_session: Session, minimal_project_ids) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    out = run_spine_workflow(db_session, did, reviewer_rejections_remaining=0)
    db_session.commit()
    expected = ["architect", "engineer", "reviewer", "documentation", "close"]
    assert out["nodes_executed"] == expected


def test_spine_happy_path_ledger_and_directive_closed(db_session: Session, minimal_project_ids) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    run_spine_workflow(db_session, did, reviewer_rejections_remaining=0)
    db_session.commit()
    ledger = TaskLedgerRepository(db_session).get_by_directive_id(did)
    d = db_session.get(Directive, did)
    assert ledger is not None
    assert ledger.current_state == TaskLifecycleState.CLOSED.value
    assert d is not None
    assert d.status == DirectiveStatus.COMPLETE.value


def test_spine_rejection_loop_extra_engineer_visit(db_session: Session, minimal_project_ids) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    out = run_spine_workflow(db_session, did, reviewer_rejections_remaining=1)
    db_session.commit()
    expected = [
        "architect",
        "engineer",
        "reviewer",
        "engineer",
        "reviewer",
        "documentation",
        "close",
    ]
    assert out["nodes_executed"] == expected


def test_spine_graph_state_history_grows(db_session: Session, minimal_project_ids) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    run_spine_workflow(db_session, did, reviewer_rejections_remaining=0)
    db_session.commit()
    gs = db_session.scalar(select(GraphState).where(GraphState.directive_id == did))
    assert gs is not None
    hist = gs.state_payload_json.get("spine_history", [])
    assert len(hist) >= 5


def test_spine_persistence_survives_new_session(db_session: Session, sqlite_engine, minimal_project_ids) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    run_spine_workflow(db_session, did, reviewer_rejections_remaining=0)
    db_session.commit()

    SessionLocal = sessionmaker(bind=sqlite_engine)
    s2 = SessionLocal()
    try:
        ledger = TaskLedgerRepository(s2).get_by_directive_id(did)
        d = s2.get(Directive, did)
        assert ledger is not None
        assert ledger.current_state == TaskLifecycleState.CLOSED.value
        assert d is not None
        assert d.status == DirectiveStatus.COMPLETE.value
    finally:
        s2.close()


def test_workflow_double_run_conflict(db_session: Session, minimal_project_ids) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    run_spine_workflow(db_session, did, reviewer_rejections_remaining=0)
    db_session.commit()
    try:
        run_spine_workflow(db_session, did, reviewer_rejections_remaining=0)
    except ValueError as e:
        assert str(e) == "workflow_already_complete"
    else:
        raise AssertionError("expected workflow_already_complete")


def test_nodes_not_public_api_surface() -> None:
    assert not hasattr(spine_mod, "architect")
    assert not hasattr(spine_mod, "engineer")
    assert hasattr(spine_mod, "run_spine_workflow")


def test_api_workflow_run(client, minimal_project_ids, auth_headers) -> None:
    ids = minimal_project_ids
    payload = {
        "project_id": str(ids["project_id"]),
        "title": "API spine",
        "status": "DRAFT",
    }
    c = client.post("/api/v1/directives/", json=payload, headers=auth_headers)
    assert c.status_code == 200, c.text
    did = c.json()["directive"]["id"]
    r = client.post(
        f"/api/v1/directives/{did}/workflow/run?reviewer_rejections_remaining=0",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["final_ledger_state"] == "CLOSED"
    assert body["directive_status"] == DirectiveStatus.COMPLETE.value
