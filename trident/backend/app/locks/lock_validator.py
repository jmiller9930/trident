"""Strict lock ownership checks (100E)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.locks.constants import LockStatus
from app.locks.exceptions import LockNotFoundError, LockOwnershipError
from app.models.file_lock import FileLock


def find_active_lock(
    session: Session,
    *,
    project_id: uuid.UUID,
    file_path_normalized: str,
) -> FileLock | None:
    return session.scalar(
        select(FileLock).where(
            FileLock.project_id == project_id,
            FileLock.file_path == file_path_normalized,
            FileLock.lock_status == LockStatus.ACTIVE.value,
            FileLock.released_at.is_(None),
        )
    )


def assert_strict_lock_ownership(
    lock: FileLock,
    *,
    directive_id: uuid.UUID,
    agent_role: str,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    file_path_normalized: str,
) -> None:
    """All dimensions must match; no partial acceptance."""
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
    if lock.lock_status != LockStatus.ACTIVE.value or lock.released_at is not None:
        raise LockNotFoundError("lock_not_active")


def get_active_lock_or_raise(
    session: Session,
    *,
    project_id: uuid.UUID,
    file_path_normalized: str,
) -> FileLock:
    lock = find_active_lock(session, project_id=project_id, file_path_normalized=file_path_normalized)
    if lock is None:
        raise LockNotFoundError("no_active_lock")
    return lock
