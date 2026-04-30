"""Nike ingest + worker dispatcher — directive 100O §15."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.enums import TaskLifecycleState
from app.models.nike_enums import NikeAttemptOutcome, NikeEventStatus, NikeOutboxStatus
from app.models.nike_event import NikeDeadLetterEvent, NikeEvent, NikeEventAttempt, NikeNotificationOutbox
from app.nike.constants import NikeEventType
from app.nike.dispatcher import drain_pending_batch, process_next_pending
from app.repositories.directive_repository import DirectiveRepository
from app.repositories.task_ledger_repository import TaskLedgerRepository
from app.schemas.directive import CreateDirectiveRequest
def _nike_settings(**kwargs: object) -> Settings:
    base: dict[str, object] = {"nike_max_attempts": 5, "nike_retry_backoff_sec": 0.0, "nike_poll_sec": 0.01}
    base.update(kwargs)
    return Settings(**base)


def _create_directive(session: Session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Nike path",
        graph_id="nike-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(session).create_directive_and_initialize(body)
    session.commit()
    return d.id


def test_nike_ingest_validation_rejects_empty_event_type(client: TestClient) -> None:
    r = client.post(
        "/api/v1/nike/events",
        json={
            "event_id": str(uuid.uuid4()),
            "event_type": "",
            "source": "test",
            "payload": {},
        },
    )
    assert r.status_code == 422


def test_nike_ingest_directive_created_requires_directive_id(client: TestClient) -> None:
    r = client.post(
        "/api/v1/nike/events",
        json={
            "event_id": str(uuid.uuid4()),
            "event_type": NikeEventType.DIRECTIVE_CREATED,
            "source": "test",
            "payload": {},
        },
    )
    assert r.status_code == 422


def test_nike_ingest_idempotent(
    client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]
) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    body = {
        "event_id": str(uuid.uuid4()),
        "event_type": NikeEventType.DIRECTIVE_CREATED,
        "source": "test",
        "directive_id": str(did),
        "correlation_id": str(uuid.uuid4()),
        "payload": {},
    }
    r1 = client.post("/api/v1/nike/events", json=body)
    r2 = client.post("/api/v1/nike/events", json=body)
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["idempotent_replay"] is True


def test_nike_get_event_roundtrip(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did = _create_directive(db_session, minimal_project_ids)
    eid = uuid.uuid4()
    ins = client.post(
        "/api/v1/nike/events",
        json={
            "event_id": str(eid),
            "event_type": NikeEventType.DIRECTIVE_CREATED,
            "source": "test",
            "directive_id": str(did),
            "payload": {"k": 1},
        },
    )
    assert ins.status_code == 200
    got = client.get(f"/api/v1/nike/events/{eid}")
    assert got.status_code == 200
    assert got.json()["event_id"] == str(eid)
    assert got.json()["payload_json"]["k"] == 1


def test_dispatcher_directive_created_invokes_spine(
    db_session: Session, minimal_project_ids: dict[str, uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.nike.dispatcher.time.sleep", lambda *_: None)
    did = _create_directive(db_session, minimal_project_ids)
    ev = NikeEvent(
        event_id=uuid.uuid4(),
        event_type=NikeEventType.DIRECTIVE_CREATED,
        source="test",
        directive_id=did,
        payload_json={},
        status=NikeEventStatus.PENDING.value,
    )
    db_session.add(ev)
    db_session.commit()

    assert process_next_pending(db_session, _nike_settings())
    db_session.commit()

    ev2 = db_session.get(NikeEvent, ev.id)
    assert ev2 is not None
    assert ev2.status == NikeEventStatus.COMPLETED.value
    ledger = TaskLedgerRepository(db_session).get_by_directive_id(did)
    assert ledger is not None
    assert ledger.current_state == TaskLifecycleState.CLOSED.value


def test_dispatcher_directive_not_found_goes_dlq_without_retry(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.nike.dispatcher.time.sleep", lambda *_: None)
    bogus = uuid.uuid4()
    ev = NikeEvent(
        event_id=uuid.uuid4(),
        event_type=NikeEventType.DIRECTIVE_CREATED,
        source="test",
        directive_id=bogus,
        payload_json={},
        status=NikeEventStatus.PENDING.value,
    )
    db_session.add(ev)
    db_session.commit()

    assert process_next_pending(db_session, _nike_settings())
    db_session.commit()

    ev2 = db_session.get(NikeEvent, ev.id)
    assert ev2 is not None
    assert ev2.status == NikeEventStatus.DEAD_LETTER.value
    dlq = db_session.scalar(select(NikeDeadLetterEvent).where(NikeDeadLetterEvent.event_pk == ev.id))
    assert dlq is not None
    assert "directive_not_found" in dlq.reason


def test_dispatcher_retry_then_dlq(
    db_session: Session, minimal_project_ids: dict[str, uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.nike.dispatcher.time.sleep", lambda *_: None)
    did = _create_directive(db_session, minimal_project_ids)
    ev = NikeEvent(
        event_id=uuid.uuid4(),
        event_type=NikeEventType.DIRECTIVE_CREATED,
        source="test",
        directive_id=did,
        payload_json={},
        status=NikeEventStatus.PENDING.value,
    )
    db_session.add(ev)
    db_session.commit()

    settings = _nike_settings(nike_max_attempts=2)
    with patch("app.nike.handlers.run_spine_workflow", side_effect=RuntimeError("forced_transient")):
        assert process_next_pending(db_session, settings)
        db_session.commit()
        assert process_next_pending(db_session, settings)
        db_session.commit()

    ev2 = db_session.get(NikeEvent, ev.id)
    assert ev2 is not None
    assert ev2.status == NikeEventStatus.DEAD_LETTER.value
    attempts = db_session.scalars(select(NikeEventAttempt).where(NikeEventAttempt.event_pk == ev.id)).all()
    assert len(attempts) >= 2
    assert any(a.outcome == NikeAttemptOutcome.RETRY_SCHEDULED.value for a in attempts)


def test_outbox_row_on_successful_directive_created(
    db_session: Session, minimal_project_ids: dict[str, uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.nike.dispatcher.time.sleep", lambda *_: None)
    did = _create_directive(db_session, minimal_project_ids)
    ev = NikeEvent(
        event_id=uuid.uuid4(),
        event_type=NikeEventType.DIRECTIVE_CREATED,
        source="test",
        directive_id=did,
        correlation_id=uuid.uuid4(),
        payload_json={},
        status=NikeEventStatus.PENDING.value,
    )
    db_session.add(ev)
    db_session.commit()

    drain_pending_batch(db_session, _nike_settings(), max_events=4)
    db_session.commit()

    ob = db_session.scalar(select(NikeNotificationOutbox).where(NikeNotificationOutbox.event_pk == ev.id))
    assert ob is not None
    assert ob.status == NikeOutboxStatus.SKIPPED_NOT_CONFIGURED.value
    assert ob.notification_type == "WORKFLOW_TRIGGERED"


def test_unhandled_event_type_completes_without_handler(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.nike.dispatcher.time.sleep", lambda *_: None)
    ev = NikeEvent(
        event_id=uuid.uuid4(),
        event_type="FUTURE_AGENT_STUB",
        source="test",
        payload_json={},
        status=NikeEventStatus.PENDING.value,
    )
    db_session.add(ev)
    db_session.commit()

    assert process_next_pending(db_session, _nike_settings())
    db_session.commit()

    ev2 = db_session.get(NikeEvent, ev.id)
    assert ev2 is not None
    assert ev2.status == NikeEventStatus.COMPLETED.value


def test_handlers_use_spine_entrypoint_only() -> None:
    import inspect

    from app.nike import handlers as nike_handlers

    src = inspect.getsource(nike_handlers.handle_directive_created)
    assert "run_spine_workflow(" in src
