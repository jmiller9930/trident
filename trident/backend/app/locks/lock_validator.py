"""Strict lock ownership checks (100E / 100P / FIX 003)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config.settings import Settings, settings as app_settings
from app.locks.constants import LockStatus
from app.locks.lock_liveness import apply_stale_transition_if_missed
from app.locks.exceptions import LockNotFoundError, LockOwnershipError
from app.models.file_lock import FileLock


def find_active_lock(
    session: Session,
    *,
    project_id: uuid.UUID,
    file_path_normalized: str,
    now: datetime | None = None,
    settings: Settings | None = None,
) -> FileLock | None:
    """ACTIVE row with valid TTL; transitions to STALE if heartbeat missed (FIX 003)."""
    cfg = settings if settings is not None else app_settings
    t = now if now is not None else datetime.now(timezone.utc)
    row = session.scalar(
        select(FileLock).where(
            FileLock.project_id == project_id,
            FileLock.file_path == file_path_normalized,
            FileLock.lock_status == LockStatus.ACTIVE.value,
            FileLock.released_at.is_(None),
            or_(FileLock.expires_at.is_(None), FileLock.expires_at > t),
        )
    )
    if row is None:
        return None
    apply_stale_transition_if_missed(session, row, cfg)
    session.refresh(row)
    if row.lock_status != LockStatus.ACTIVE.value or row.released_at is not None:
        return None
    return row


def assert_strict_lock_ownership(
    lock: FileLock,
    *,
    directive_id: uuid.UUID,
    agent_role: str,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    file_path_normalized: str,
    require_active_for_editing: bool = True,
) -> None:
    """All dimensions must match. Release allows STALE_PENDING_RECOVERY when require_active_for_editing=False."""
    if lock.project_id != project_id:
        raise LockOwnershipError("project_mismatch")
    if lock.directive_id != directive_id:
        raise LockOwnershipError("directive_mismatch")
    if lock.locked_by_agent_role != agent_role.strip():
        raise LockOwnershipError("agent_role_mismatch")
    if lock.locked_by_user_id != user_id:
        raise LockOwnershipError("user_mismatch")
    if lock.file_path != file_path_normalized:
        raise LockOwnershipError("path_mismatch")
    if lock.released_at is not None:
        raise LockNotFoundError("lock_not_active")
    if require_active_for_editing:
        if lock.lock_status != LockStatus.ACTIVE.value:
            raise LockNotFoundError("lock_not_active")
    else:
        if lock.lock_status not in (
            LockStatus.ACTIVE.value,
            LockStatus.STALE_PENDING_RECOVERY.value,
        ):
            raise LockNotFoundError("lock_not_active")


def get_active_lock_or_raise(
    session: Session,
    *,
    project_id: uuid.UUID,
    file_path_normalized: str,
    settings: Settings | None = None,
) -> FileLock:
    cfg = settings if settings is not None else app_settings
    lock = find_active_lock(
        session,
        project_id=project_id,
        file_path_normalized=file_path_normalized,
        settings=cfg,
    )
    if lock is None:
        raise LockNotFoundError("no_active_lock")
    return lock
