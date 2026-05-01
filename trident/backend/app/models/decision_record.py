"""DecisionRecord — append-only governed decision records (TRIDENT_DECISION_ENGINE_001)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base


class DecisionRecommendation(StrEnum):
    ACCEPT_PATCH = "ACCEPT_PATCH"
    REJECT_PATCH = "REJECT_PATCH"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    EXECUTE_PATCH = "EXECUTE_PATCH"
    CREATE_VALIDATION = "CREATE_VALIDATION"
    SIGNOFF = "SIGNOFF"
    BLOCKED = "BLOCKED"
    NO_ACTION = "NO_ACTION"


class DecisionRecord(Base):
    __tablename__ = "decision_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    directive_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("directives.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("patch_proposals.id", ondelete="SET NULL"), nullable=True
    )

    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float(), nullable=False)
    summary: Mapped[str] = mapped_column(String(4096), nullable=False)

    evidence_json: Mapped[list[Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    blocking_reasons_json: Mapped[list[Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
