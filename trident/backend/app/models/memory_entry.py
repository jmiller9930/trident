from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base
from app.memory.constants import MemoryVectorState


class MemoryEntry(Base):
    """Structured memory row (100D); vector sidecar in Chroma keyed by id."""

    __tablename__ = "memory_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("directives.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_ledger_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("task_ledger.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_role: Mapped[str] = mapped_column(String(32), nullable=False)
    memory_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body_text: Mapped[str] = mapped_column(Text(), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    chroma_document_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    memory_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    vector_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MemoryVectorState.VECTOR_PENDING.value,
    )
    vector_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    vector_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
