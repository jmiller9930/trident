"""Nike event ingest and read API (100O §8)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.nike_enums import NikeEventStatus
from app.models.nike_event import NikeEvent
from app.nike.constants import NikeEventType
from app.schemas.nike_event import (
    NikeEventIngestRequest,
    NikeEventIngestResponse,
    NikeEventListResponse,
    NikeEventSnapshot,
)

router = APIRouter()


def _require_directive_id_for_type(body: NikeEventIngestRequest) -> None:
    if body.event_type != NikeEventType.DIRECTIVE_CREATED:
        return
    if body.directive_id is not None:
        return
    p = body.payload
    if isinstance(p, dict) and p.get("directive_id") is not None:
        return
    raise HTTPException(
        status_code=422,
        detail="directive_id is required for DIRECTIVE_CREATED (envelope or payload.directive_id)",
    )


@router.post("/events", response_model=NikeEventIngestResponse)
def ingest_event(body: NikeEventIngestRequest, db: Session = Depends(get_db)) -> NikeEventIngestResponse:
    _require_directive_id_for_type(body)
    existing = db.scalar(select(NikeEvent).where(NikeEvent.event_id == body.event_id))
    if existing is not None:
        return NikeEventIngestResponse(
            id=existing.id,
            event_id=existing.event_id,
            status=existing.status,
            idempotent_replay=True,
        )

    row = NikeEvent(
        event_id=body.event_id,
        event_type=body.event_type,
        source=body.source,
        workspace_id=body.workspace_id,
        project_id=body.project_id,
        directive_id=body.directive_id,
        task_id=body.task_id,
        correlation_id=body.correlation_id,
        payload_json=body.payload,
        status=NikeEventStatus.PENDING.value,
    )
    db.add(row)
    db.flush()
    return NikeEventIngestResponse(
        id=row.id,
        event_id=row.event_id,
        status=row.status,
        idempotent_replay=False,
    )


@router.get("/events/{event_id}", response_model=NikeEventSnapshot)
def get_event_by_event_id(event_id: uuid.UUID, db: Session = Depends(get_db)) -> NikeEventSnapshot:
    row = db.scalar(select(NikeEvent).where(NikeEvent.event_id == event_id))
    if row is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    return NikeEventSnapshot.model_validate(row)


@router.get("/events", response_model=NikeEventListResponse)
def list_events(
    db: Session = Depends(get_db),
    directive_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> NikeEventListResponse:
    q = select(NikeEvent)
    if directive_id is not None:
        q = q.where(NikeEvent.directive_id == directive_id)
    q = q.order_by(NikeEvent.created_at.desc()).limit(limit)
    rows = list(db.scalars(q).all())
    return NikeEventListResponse(items=[NikeEventSnapshot.model_validate(r) for r in rows])
