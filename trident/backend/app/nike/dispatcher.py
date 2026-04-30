"""Nike worker dispatcher — poll, route, attempts, DLQ, outbox (100O)."""

from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.nike_enums import NikeAttemptOutcome, NikeEventStatus, NikeOutboxChannel, NikeOutboxStatus
from app.models.nike_event import NikeDeadLetterEvent, NikeEvent, NikeEventAttempt, NikeNotificationOutbox
from app.nike import handlers as handlers_mod
from app.nike.constants import NikeEventType
from app.nike.handlers import handler_for

if TYPE_CHECKING:
    pass

logger = logging.getLogger("trident.nike")

# Failures that never benefit from retry (100O policy).
_NON_RETRY_VALUE_ERRORS = frozenset({"directive_not_found", "directive_id_required"})


def _correlation_token(ev: NikeEvent) -> str:
    return str(ev.correlation_id) if ev.correlation_id else ""


def _attempt_count(session: Session, event_pk: uuid.UUID) -> int:
    n = session.scalar(select(func.count()).select_from(NikeEventAttempt).where(NikeEventAttempt.event_pk == event_pk))
    return int(n or 0)


def claim_pending_event(session: Session) -> NikeEvent | None:
    stmt = (
        select(NikeEvent)
        .where(NikeEvent.status == NikeEventStatus.PENDING.value)
        .order_by(NikeEvent.created_at.asc())
        .limit(1)
    )
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    else:
        stmt = stmt.with_for_update()
    ev = session.scalars(stmt).first()
    if ev is None:
        return None
    ev.status = NikeEventStatus.PROCESSING.value
    session.flush()
    logger.info(
        "event=nike_claimed correlation_id=%s event_id=%s event_type=%s internal_id=%s",
        _correlation_token(ev),
        ev.event_id,
        ev.event_type,
        ev.id,
    )
    return ev


def _move_to_dead_letter(
    session: Session,
    ev: NikeEvent,
    *,
    reason: str,
    failed_attempt_count: int,
) -> None:
    session.add(
        NikeDeadLetterEvent(
            event_pk=ev.id,
            reason=reason[:2048],
            failed_attempt_count=failed_attempt_count,
            payload_snapshot_json={
                "event_id": str(ev.event_id),
                "event_type": ev.event_type,
                "source": ev.source,
                "payload_json": ev.payload_json,
            },
        )
    )
    ev.status = NikeEventStatus.DEAD_LETTER.value
    session.flush()
    logger.info(
        "event=nike_dead_letter correlation_id=%s event_id=%s reason=%s attempts=%s",
        _correlation_token(ev),
        ev.event_id,
        reason,
        failed_attempt_count,
    )


def _append_workflow_outbox(session: Session, ev: NikeEvent) -> None:
    did = handlers_mod.directive_id_for_event(ev)
    session.add(
        NikeNotificationOutbox(
            event_pk=ev.id,
            channel=NikeOutboxChannel.INTERNAL.value,
            notification_type="WORKFLOW_TRIGGERED",
            payload_json={
                "event_type": ev.event_type,
                "directive_id": str(did) if did else None,
                "correlation_id": _correlation_token(ev) or None,
            },
            status=NikeOutboxStatus.SKIPPED_NOT_CONFIGURED.value,
        )
    )


def dispatch_one(session: Session, settings: Settings, ev: NikeEvent) -> None:
    """Run routing + handler for a claimed event; mutates `ev` and related rows."""
    attempt_no = _attempt_count(session, ev.id) + 1
    fn = handler_for(ev.event_type)

    if fn is None:
        session.add(
            NikeEventAttempt(
                event_pk=ev.id,
                attempt_no=attempt_no,
                outcome=NikeAttemptOutcome.SUCCESS.value,
                error_detail=None,
            )
        )
        ev.status = NikeEventStatus.COMPLETED.value
        session.flush()
        logger.info(
            "event=nike_dispatch_unhandled_noop correlation_id=%s event_id=%s event_type=%s",
            _correlation_token(ev),
            ev.event_id,
            ev.event_type,
        )
        return

    try:
        fn(session, ev)
    except ValueError as e:
        code = str(e)
        if code in _NON_RETRY_VALUE_ERRORS:
            session.add(
                NikeEventAttempt(
                    event_pk=ev.id,
                    attempt_no=attempt_no,
                    outcome=NikeAttemptOutcome.FAILED.value,
                    error_detail=code[:4096],
                )
            )
            _move_to_dead_letter(session, ev, reason=code, failed_attempt_count=attempt_no)
            logger.info(
                "event=nike_dispatch_failed_nonretry correlation_id=%s event_id=%s detail=%s",
                _correlation_token(ev),
                ev.event_id,
                code,
            )
            return
        logger.warning(
            "event=nike_dispatch_value_error correlation_id=%s event_id=%s detail=%s",
            _correlation_token(ev),
            ev.event_id,
            code,
        )
        _schedule_retry_or_dlq(session, settings, ev, attempt_no, detail=code)
        return
    except Exception:
        logger.exception(
            "event=nike_dispatch_exception correlation_id=%s event_id=%s attempt=%s",
            _correlation_token(ev),
            ev.event_id,
            attempt_no,
        )
        _schedule_retry_or_dlq(session, settings, ev, attempt_no, detail="exception")
        return

    session.add(
        NikeEventAttempt(
            event_pk=ev.id,
            attempt_no=attempt_no,
            outcome=NikeAttemptOutcome.SUCCESS.value,
            error_detail=None,
        )
    )
    if ev.event_type == NikeEventType.DIRECTIVE_CREATED:
        _append_workflow_outbox(session, ev)
    ev.status = NikeEventStatus.COMPLETED.value
    session.flush()
    logger.info(
        "event=nike_dispatch_success correlation_id=%s event_id=%s event_type=%s attempt=%s",
        _correlation_token(ev),
        ev.event_id,
        ev.event_type,
        attempt_no,
    )


def _schedule_retry_or_dlq(session: Session, settings: Settings, ev: NikeEvent, attempt_no: int, *, detail: str) -> None:
    if attempt_no >= settings.nike_max_attempts:
        session.add(
            NikeEventAttempt(
                event_pk=ev.id,
                attempt_no=attempt_no,
                outcome=NikeAttemptOutcome.FAILED.value,
                error_detail=detail[:4096],
            )
        )
        _move_to_dead_letter(
            session,
            ev,
            reason=f"max_attempts_exceeded:{detail}",
            failed_attempt_count=attempt_no,
        )
        logger.info(
            "event=nike_retry_exhausted correlation_id=%s event_id=%s attempts=%s",
            _correlation_token(ev),
            ev.event_id,
            attempt_no,
        )
        return

    session.add(
        NikeEventAttempt(
            event_pk=ev.id,
            attempt_no=attempt_no,
            outcome=NikeAttemptOutcome.RETRY_SCHEDULED.value,
            error_detail=detail[:4096],
        )
    )
    # Bounded linear backoff before the row becomes eligible again (single-worker friendly).
    delay = min(settings.nike_retry_backoff_sec * float(attempt_no), 60.0)
    time.sleep(delay)
    ev.status = NikeEventStatus.PENDING.value
    session.flush()
    logger.info(
        "event=nike_retry_scheduled correlation_id=%s event_id=%s next_attempt=%s backoff_sec=%s",
        _correlation_token(ev),
        ev.event_id,
        attempt_no + 1,
        delay,
    )


def process_next_pending(session: Session, settings: Settings) -> bool:
    ev = claim_pending_event(session)
    if ev is None:
        return False
    dispatch_one(session, settings, ev)
    return True


def drain_pending_batch(session: Session, settings: Settings, *, max_events: int = 16) -> int:
    """Process up to `max_events` pending rows in one transaction (tests / tight loops)."""
    done = 0
    for _ in range(max_events):
        if not process_next_pending(session, settings):
            break
        done += 1
    return done
