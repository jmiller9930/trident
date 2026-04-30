"""Monotonic memory_sequence allocation (FIX 004)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory_sequence_anchor import MemorySequenceAnchor


def allocate_memory_sequence(session: Session) -> int:
    anchor = session.scalar(
        select(MemorySequenceAnchor)
        .where(MemorySequenceAnchor.id == 1)
        .with_for_update(of=MemorySequenceAnchor)
    )
    if anchor is None:
        session.add(MemorySequenceAnchor(id=1, next_sequence=0))
        session.flush()
        anchor = session.scalar(
            select(MemorySequenceAnchor)
            .where(MemorySequenceAnchor.id == 1)
            .with_for_update(of=MemorySequenceAnchor)
        )
    assert anchor is not None
    anchor.next_sequence += 1
    session.flush()
    return int(anchor.next_sequence)
