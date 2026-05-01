"""FIX 003 — heartbeat miss → STALE_PENDING_RECOVERY (server-authoritative)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.locks.constants import LockStatus
from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType
from app.models.file_lock import FileLock
from app.repositories.audit_repository import AuditRepository


def _as_utc_aware(dt: datetime) -> datetime:
    """SQLite may return naive datetimes; treat naive as UTC for comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def apply_stale_transition_if_missed(session: Session, lock: FileLock, cfg: Settings) -> None:
    """If ACTIVE and heartbeat overdue, set STALE_PENDING_RECOVERY and audit LOCK_STALE."""
    if lock.lock_status != LockStatus.ACTIVE.value or lock.released_at is not None:
        return
    miss = cfg.lock_heartbeat_miss_sec
    if miss <= 0:
        return
    lh = lock.last_heartbeat_at
    if lh is None:
        return
    now = datetime.now(timezone.utc)
    lh_utc = _as_utc_aware(lh)
    if (now - lh_utc).total_seconds() <= miss:
        return

    directive = session.get(Directive, lock.directive_id)
    ws_id = directive.workspace_id if directive else None
    lock.lock_status = LockStatus.STALE_PENDING_RECOVERY.value
    AuditRepository(session).record(
        event_type=AuditEventType.LOCK_STALE,
        event_payload={
            "lock_id": str(lock.id),
            "file_path": lock.file_path,
            "miss_sec": miss,
            "last_heartbeat_at": lh.isoformat(),
        },
        actor_type=AuditActorType.SYSTEM,
        actor_id="trident-api",
        workspace_id=ws_id,
        project_id=lock.project_id,
        directive_id=lock.directive_id,
    )
    session.flush()


def archive_stale_rows_before_acquire(
    session: Session,
    *,
    project_id: uuid.UUID,
    file_path_normalized: str,
    cfg: Settings,
    acquiring_user_id: uuid.UUID,
    acquiring_directive_id: uuid.UUID,
) -> None:
    """Close STALE rows on same path when a different principal acquires (takeover audit)."""
    from sqlalchemy import select

    rows = list(
        session.scalars(
            select(FileLock).where(
                FileLock.project_id == project_id,
                FileLock.file_path == file_path_normalized,
                FileLock.lock_status == LockStatus.STALE_PENDING_RECOVERY.value,
                FileLock.released_at.is_(None),
            )
        ).all()
    )
    audit = AuditRepository(session)
    now = datetime.now(timezone.utc)
    for row in rows:
        same_owner = row.locked_by_user_id == acquiring_user_id and row.directive_id == acquiring_directive_id
        if same_owner:
            continue
        directive = session.get(Directive, row.directive_id)
        ws_id = directive.workspace_id if directive else None
        row.lock_status = LockStatus.EXPIRED.value
        row.released_at = now
        audit.record(
            event_type=AuditEventType.LOCK_TAKEOVER,
            event_payload={
                "prior_lock_id": str(row.id),
                "file_path": file_path_normalized,
                "new_directive_id": str(acquiring_directive_id),
                "new_user_id": str(acquiring_user_id),
            },
            actor_type=AuditActorType.SYSTEM,
            actor_id="trident-api",
            workspace_id=ws_id,
            project_id=project_id,
            directive_id=row.directive_id,
        )
    if rows:
        session.flush()
