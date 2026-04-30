"""Distinct audit timestamps within one DB transaction (Postgres: server now() is transaction-stable)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

_TICK_KEY = "_audit_created_at_tick"


def next_audit_created_at(session: Session) -> datetime:
    """Monotonic microsecond offsets so ORDER BY created_at matches emission order."""
    base = datetime.now(timezone.utc)
    tick = session.info.get(_TICK_KEY, 0) + 1
    session.info[_TICK_KEY] = tick
    return base + timedelta(microseconds=tick)
