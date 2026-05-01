"""Acquire / release file locks with audits (100E / 100P / FIX 003)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings, settings as app_settings
from app.locks.constants import LockStatus
from app.locks.exceptions import LockConflictError, LockNotFoundError, LockOwnershipError
from app.locks.lock_liveness import archive_stale_rows_before_acquire
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


def _parse_force_release_admins(raw: str) -> set[uuid.UUID]:
    out: set[uuid.UUID] = set()
    for part in (raw or "").split(","):
        p = part.strip()
        if not p:
            continue
        try:
            out.add(uuid.UUID(p))
        except ValueError:
            continue
    return out


class LockService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._audit = AuditRepository(session)
        self._settings = settings if settings is not None else app_settings

    def _expire_stale_locks_for_path(self, *, project_id: uuid.UUID, fp: str) -> None:
        """Release ACTIVE rows past expires_at so TTL locks do not block unique index."""
        now = datetime.now(timezone.utc)
        rows = list(
            self._session.scalars(
                select(FileLock).where(
                    FileLock.project_id == project_id,
                    FileLock.file_path == fp,
                    FileLock.lock_status == LockStatus.ACTIVE.value,
                    FileLock.released_at.is_(None),
                    FileLock.expires_at.is_not(None),
                    FileLock.expires_at <= now,
                )
            ).all()
        )
        for lock in rows:
            directive = self._session.get(Directive, lock.directive_id)
            ws_id = directive.workspace_id if directive else None
            lock.lock_status = LockStatus.RELEASED.value
            lock.released_at = now
            self._audit.record(
                event_type=AuditEventType.LOCK_RELEASED,
                event_payload={"reason": "ttl_expired", "lock_id": str(lock.id), "file_path": fp},
                actor_type=AuditActorType.SYSTEM,
                actor_id="trident-api",
                workspace_id=ws_id,
                project_id=project_id,
                directive_id=lock.directive_id,
            )
        if rows:
            self._session.flush()

    def acquire(
        self,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        agent_role: str,
        user_id: uuid.UUID,
        relative_file_path: str,
        ttl_seconds: int | None = None,
    ) -> FileLock:
        """Create ACTIVE lock; rejects duplicate active (project_id, file_path). directive_id required."""
        fp = normalize_relative_file_path(relative_file_path)
        directive = self._session.get(Directive, directive_id)
        if directive is None:
            raise ValueError("directive_not_found")
        if directive.project_id != project_id:
            raise ValueError("directive_project_mismatch")

        archive_stale_rows_before_acquire(
            self._session,
            project_id=project_id,
            file_path_normalized=fp,
            cfg=self._settings,
            acquiring_user_id=user_id,
            acquiring_directive_id=directive_id,
        )

        self._expire_stale_locks_for_path(project_id=project_id, fp=fp)

        existing = find_active_lock(
            self._session,
            project_id=project_id,
            file_path_normalized=fp,
            settings=self._settings,
        )
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

        now = datetime.now(timezone.utc)
        exp: datetime | None = None
        if ttl_seconds is not None and ttl_seconds > 0:
            exp = now + timedelta(seconds=int(ttl_seconds))
        row = FileLock(
            project_id=project_id,
            directive_id=directive_id,
            file_path=fp,
            locked_by_agent_role=agent_role.strip(),
            locked_by_user_id=user_id,
            lock_status=LockStatus.ACTIVE.value,
            released_at=None,
            expires_at=exp,
            last_heartbeat_at=now,
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

    def heartbeat(
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
                require_active_for_editing=True,
            )
        except (LockOwnershipError, LockNotFoundError):
            self._audit.record(
                event_type=AuditEventType.LOCK_REJECTED,
                event_payload={"reason": "heartbeat_ownership_mismatch", "lock_id": str(lock_id)},
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
        now = datetime.now(timezone.utc)
        lock.last_heartbeat_at = now
        self._session.flush()

        self._audit.record(
            event_type=AuditEventType.LOCK_HEARTBEAT,
            event_payload={"lock_id": str(lock_id), "file_path": fp},
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{agent_role.strip()}",
            workspace_id=workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )
        return lock

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
        was_stale = lock.lock_status == LockStatus.STALE_PENDING_RECOVERY.value
        try:
            assert_strict_lock_ownership(
                lock,
                directive_id=directive_id,
                agent_role=agent_role,
                user_id=user_id,
                project_id=project_id,
                file_path_normalized=fp,
                require_active_for_editing=False,
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

        now = datetime.now(timezone.utc)
        lock.lock_status = LockStatus.RELEASED.value
        lock.released_at = lock.released_at or now
        self._session.flush()

        ev = AuditEventType.LOCK_RECOVERED if was_stale else AuditEventType.LOCK_RELEASED
        self._audit.record(
            event_type=ev,
            event_payload={"lock_id": str(lock_id), "file_path": fp},
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{agent_role.strip()}",
            workspace_id=workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )
        return lock

    def force_release(
        self,
        *,
        lock_id: uuid.UUID,
        project_id: uuid.UUID,
        admin_user_id: uuid.UUID,
    ) -> FileLock:
        admins = _parse_force_release_admins(self._settings.lock_force_release_admin_user_ids)
        if admin_user_id not in admins:
            raise PermissionError("force_release_forbidden")

        lock = self._session.get(FileLock, lock_id)
        if lock is None:
            raise LockNotFoundError("lock_row_missing")
        if lock.project_id != project_id:
            raise LockOwnershipError("project_mismatch")
        if lock.released_at is not None:
            raise LockNotFoundError("lock_not_active")

        directive = self._session.get(Directive, lock.directive_id)
        workspace_id = directive.workspace_id if directive else None

        now = datetime.now(timezone.utc)
        lock.lock_status = LockStatus.FORCE_RELEASED.value
        lock.released_at = now
        self._session.flush()

        self._audit.record(
            event_type=AuditEventType.LOCK_FORCE_RELEASED,
            event_payload={
                "lock_id": str(lock_id),
                "file_path": lock.file_path,
                "admin_user_id": str(admin_user_id),
            },
            actor_type=AuditActorType.USER,
            actor_id=str(admin_user_id),
            workspace_id=workspace_id,
            project_id=project_id,
            directive_id=lock.directive_id,
        )
        return lock
