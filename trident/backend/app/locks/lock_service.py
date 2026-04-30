"""Acquire / release file locks with audits (100E)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.locks.constants import LockStatus
from app.locks.exceptions import LockConflictError, LockNotFoundError, LockOwnershipError
from app.locks.lock_validator import assert_strict_lock_ownership, find_active_lock
from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType
from app.models.file_lock import FileLock
from app.repositories.audit_repository import AuditRepository


def normalize_relative_file_path(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty_file_path")
    p = Path(s)
    if p.is_absolute():
        raise ValueError("absolute_file_path")
    parts = p.as_posix().split("/")
    if ".." in parts:
        raise ValueError("path_traversal_forbidden")
    return p.as_posix()


class LockService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditRepository(session)

    def acquire(
        self,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        agent_role: str,
        user_id: uuid.UUID,
        relative_file_path: str,
    ) -> FileLock:
        """Create ACTIVE lock; rejects duplicate active (project_id, file_path). directive_id required."""
        fp = normalize_relative_file_path(relative_file_path)
        directive = self._session.get(Directive, directive_id)
        if directive is None:
            raise ValueError("directive_not_found")
        if directive.project_id != project_id:
            raise ValueError("directive_project_mismatch")

        existing = find_active_lock(self._session, project_id=project_id, file_path_normalized=fp)
        if existing is not None:
            self._audit.record(
                event_type=AuditEventType.LOCK_REJECTED,
                event_payload={
                    "reason": "active_lock_exists",
                    "project_id": str(project_id),
                    "file_path": fp,
                    "existing_lock_id": str(existing.id),
                },
                actor_type=AuditActorType.AGENT,
                actor_id=f"agent:{agent_role.strip()}",
                workspace_id=directive.workspace_id,
                project_id=project_id,
                directive_id=directive_id,
            )
            self._session.flush()
            self._session.commit()
            raise LockConflictError()

        row = FileLock(
            project_id=project_id,
            directive_id=directive_id,
            file_path=fp,
            locked_by_agent_role=agent_role.strip(),
            locked_by_user_id=user_id,
            lock_status=LockStatus.ACTIVE.value,
            released_at=None,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            self._audit.record(
                event_type=AuditEventType.LOCK_REJECTED,
                event_payload={"reason": "unique_active_lock_violation", "project_id": str(project_id), "file_path": fp},
                actor_type=AuditActorType.AGENT,
                actor_id=f"agent:{agent_role.strip()}",
                workspace_id=directive.workspace_id,
                project_id=project_id,
                directive_id=directive_id,
            )
            self._session.flush()
            self._session.commit()
            raise LockConflictError() from None

        self._audit.record(
            event_type=AuditEventType.LOCK_CREATED,
            event_payload={
                "lock_id": str(row.id),
                "file_path": fp,
                "agent_role": agent_role.strip(),
                "user_id": str(user_id),
            },
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{agent_role.strip()}",
            workspace_id=directive.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )
        return row

    def release(
        self,
        *,
        lock_id: uuid.UUID,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        agent_role: str,
        user_id: uuid.UUID,
        relative_file_path: str,
    ) -> FileLock:
        fp = normalize_relative_file_path(relative_file_path)
        lock = self._session.get(FileLock, lock_id)
        if lock is None:
            raise LockNotFoundError("lock_row_missing")
        try:
            assert_strict_lock_ownership(
                lock,
                directive_id=directive_id,
                agent_role=agent_role,
                user_id=user_id,
                project_id=project_id,
                file_path_normalized=fp,
            )
        except (LockOwnershipError, LockNotFoundError):
            self._audit.record(
                event_type=AuditEventType.LOCK_REJECTED,
                event_payload={"reason": "release_ownership_mismatch", "lock_id": str(lock_id)},
                actor_type=AuditActorType.AGENT,
                actor_id=f"agent:{agent_role.strip()}",
                workspace_id=None,
                project_id=project_id,
                directive_id=directive_id,
            )
            self._session.flush()
            self._session.commit()
            raise

        directive = self._session.get(Directive, directive_id)
        workspace_id = directive.workspace_id if directive else None

        lock.lock_status = LockStatus.RELEASED.value
        lock.released_at = lock.released_at or datetime.now(timezone.utc)
        self._session.flush()

        self._audit.record(
            event_type=AuditEventType.LOCK_RELEASED,
            event_payload={"lock_id": str(lock_id), "file_path": fp},
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{agent_role.strip()}",
            workspace_id=workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )
        return lock
