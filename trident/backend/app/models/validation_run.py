"""ValidationRun — post-commit validation / bug-check tracking (VALIDATION_001).

Lifecycle: PENDING → RUNNING → PASSED | FAILED | WAIVED
PASSED, FAILED, WAIVED are terminal and immutable.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base


class ValidationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    WAIVED = "WAIVED"


class ValidationRunType(StrEnum):
    MANUAL = "MANUAL"
    SMOKE = "SMOKE"
    TEST_SUITE = "TEST_SUITE"
    LINT = "LINT"
    TYPECHECK = "TYPECHECK"
    SECURITY = "SECURITY"


_TERMINAL_STATUSES = frozenset({
    ValidationStatus.PASSED,
    ValidationStatus.FAILED,
    ValidationStatus.WAIVED,
})


class ValidationRun(Base):
    """A single validation execution or manual sign-off record for a directive."""

    __tablename__ = "validation_runs"

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

    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ValidationStatus.PENDING.value)
    validation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )

    started_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
