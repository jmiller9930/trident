"""Deterministic event_type → handler routing (100O). No LLM / MCP / filesystem."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.nike.constants import NikeEventType
from app.workflow.spine import run_spine_workflow

if TYPE_CHECKING:
    from app.models.nike_event import NikeEvent

HandlerFn = Callable[[Session, "NikeEvent"], None]

_REGISTRY: dict[str, HandlerFn] = {}


def register_handler(event_type: str) -> Callable[[HandlerFn], HandlerFn]:
    def _wrap(fn: HandlerFn) -> HandlerFn:
        _REGISTRY[event_type] = fn
        return fn

    return _wrap


def handler_for(event_type: str) -> HandlerFn | None:
    return _REGISTRY.get(event_type)


def directive_id_for_event(ev: "NikeEvent") -> uuid.UUID | None:
    if ev.directive_id is not None:
        return ev.directive_id
    p = ev.payload_json
    if not isinstance(p, dict):
        return None
    raw = p.get("directive_id")
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


@register_handler(NikeEventType.DIRECTIVE_CREATED)
def handle_directive_created(session: Session, ev: "NikeEvent") -> None:
    did = directive_id_for_event(ev)
    if did is None:
        raise ValueError("directive_id_required")

    rem = 0
    if isinstance(ev.payload_json, dict):
        try:
            rem = int(ev.payload_json.get("reviewer_rejections_remaining", 0))
        except (TypeError, ValueError):
            rem = 0

    try:
        run_spine_workflow(session, did, reviewer_rejections_remaining=rem)
    except ValueError as e:
        if str(e) == "workflow_already_complete":
            return
        raise
