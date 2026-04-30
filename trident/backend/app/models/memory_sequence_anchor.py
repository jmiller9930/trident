"""Singleton row for monotonic global memory_sequence (FIX 004)."""

from __future__ import annotations

from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MemorySequenceAnchor(Base):
    __tablename__ = "memory_sequence_anchor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    next_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
