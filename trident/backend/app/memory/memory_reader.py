"""Scoped memory reads + access audit + optional Chroma retrieval (100D)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import Settings, settings as app_settings
from app.models.audit_event import AuditEvent
from app.models.directive import Directive
from app.models.handoff import Handoff
from app.models.memory_entry import MemoryEntry
from app.models.proof_object import ProofObject
from app.models.task_ledger import TaskLedger
from app.repositories.audit_repository import AuditRepository
from app.models.enums import AuditActorType, AuditEventType

from app.memory.vector_service import VectorMemoryService


class MemoryReader:
    def __init__(self, session: Session, cfg: Settings | None = None) -> None:
        self._session = session
        self._cfg = cfg if cfg is not None else app_settings
        self._audit = AuditRepository(session)
        self._vector = VectorMemoryService(self._cfg)

    def _record_read(self, *, scope: str, project_id: uuid.UUID | None, directive_id: uuid.UUID | None) -> None:
        self._audit.record(
            event_type=AuditEventType.MEMORY_READ_ACCESS,
            event_payload={"scope": scope, "project_id": str(project_id) if project_id else None, "directive_id": str(directive_id) if directive_id else None},
            actor_type=AuditActorType.SYSTEM,
            actor_id="memory_api:read",
            workspace_id=None,
            project_id=project_id,
            directive_id=directive_id,
        )

    def read_project(self, project_id: uuid.UUID, *, limit: int = 200) -> dict[str, Any]:
        self._record_read(scope="project", project_id=project_id, directive_id=None)
        q = (
            select(MemoryEntry)
            .where(MemoryEntry.project_id == project_id)
            .order_by(MemoryEntry.created_at.desc())
            .limit(limit)
        )
        rows = list(self._session.scalars(q).all())
        nd = self._session.scalar(select(func.count()).select_from(Directive).where(Directive.project_id == project_id)) or 0
        return {
            "project_id": str(project_id),
            "directive_count": int(nd),
            "memory_entries": [_entry_summary(r) for r in rows],
        }

    def read_directive(
        self,
        directive_id: uuid.UUID,
        *,
        vector_query: str | None = None,
        vector_top_k: int = 8,
    ) -> dict[str, Any]:
        d = self._session.get(Directive, directive_id)
        if d is None:
            return {"error": "directive_not_found"}
        ledger = self._session.scalar(select(TaskLedger).where(TaskLedger.directive_id == directive_id))
        if ledger is None:
            return {"error": "task_ledger_not_found"}

        self._record_read(scope="directive", project_id=d.project_id, directive_id=directive_id)

        entries = list(
            self._session.scalars(
                select(MemoryEntry)
                .where(MemoryEntry.directive_id == directive_id)
                .order_by(MemoryEntry.created_at.desc())
                .limit(200)
            ).all()
        )
        handoffs = list(
            self._session.scalars(select(Handoff).where(Handoff.directive_id == directive_id).order_by(Handoff.created_at.desc()).limit(50)).all()
        )
        proofs = list(
            self._session.scalars(select(ProofObject).where(ProofObject.directive_id == directive_id).order_by(ProofObject.created_at.desc()).limit(50)).all()
        )

        vector_hits: dict[str, Any] | None = None
        if vector_query and vector_query.strip():
            vector_hits = self._vector.query_similar(
                vector_query.strip(),
                project_id=str(d.project_id),
                directive_id=str(directive_id),
                top_k=vector_top_k,
            )

        return {
            "directive_id": str(directive_id),
            "project_id": str(d.project_id),
            "workspace_id": str(d.workspace_id),
            "task_ledger": {
                "id": str(ledger.id),
                "current_state": ledger.current_state,
                "current_agent_role": ledger.current_agent_role,
            },
            "memory_entries": [_entry_summary(r) for r in entries],
            "handoffs": [_handoff_summary(h) for h in handoffs],
            "proof_objects": [_proof_summary(p) for p in proofs],
            "vector_query_hits": vector_hits,
        }


def _entry_summary(r: MemoryEntry) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "directive_id": str(r.directive_id),
        "task_ledger_id": str(r.task_ledger_id),
        "agent_role": r.agent_role,
        "memory_kind": r.memory_kind,
        "title": r.title,
        "body_preview": r.body_text[:500] + ("…" if len(r.body_text) > 500 else ""),
        "created_at": r.created_at.isoformat(),
    }


def _handoff_summary(h: Handoff) -> dict[str, Any]:
    return {
        "id": str(h.id),
        "from_agent_role": h.from_agent_role,
        "to_agent_role": h.to_agent_role,
        "requires_ack": h.requires_ack,
        "acknowledged_at": h.acknowledged_at.isoformat() if h.acknowledged_at else None,
        "created_at": h.created_at.isoformat(),
    }


def _proof_summary(p: ProofObject) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "proof_type": p.proof_type,
        "proof_summary": p.proof_summary,
        "created_at": p.created_at.isoformat(),
    }
