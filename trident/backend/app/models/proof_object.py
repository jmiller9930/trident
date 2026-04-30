from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


class ProofObject(Base):
    __tablename__ = "proof_objects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    directive_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("directives.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proof_type: Mapped[str] = mapped_column(String(64), nullable=False)
    proof_uri: Mapped[str | None] = mapped_column(Text(), nullable=True)
    proof_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    proof_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by_agent_role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
