"""Graph-governed memory writes + audit (100D) + FIX 004 vector lifecycle."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import Settings, settings as app_settings
from app.memory.constants import MemoryVectorState
from app.memory.sequence import allocate_memory_sequence
from app.models.enums import AuditActorType, AuditEventType, TaskLifecycleState
from app.models.memory_entry import MemoryEntry
from app.repositories.audit_repository import AuditRepository
from app.workflow.persistence import load_spine_context

from app.memory.exceptions import MemoryWriteForbidden
from app.memory.vector_service import VectorMemoryService

logger = logging.getLogger("trident.memory.writer")


class MemoryWriter:
    def __init__(self, session: Session, cfg: Settings | None = None) -> None:
        self._session = session
        self._cfg = cfg if cfg is not None else app_settings
        self._audit = AuditRepository(session)
        self._vector = VectorMemoryService(self._cfg)

    def _validate_graph_context(
        self,
        *,
        directive_id: uuid.UUID,
        task_ledger_id: uuid.UUID,
        agent_role: str,
        workflow_run_nonce: str,
    ) -> tuple[Any, Any, Any]:
        ctx = load_spine_context(self._session, directive_id)
        if ctx is None:
            raise MemoryWriteForbidden("directive_not_found")
        directive, ledger, graph = ctx
        if ledger.id != task_ledger_id:
            raise MemoryWriteForbidden("task_id_mismatch")
        if ledger.current_state == TaskLifecycleState.CLOSED.value:
            raise MemoryWriteForbidden("workflow_complete_no_writes")
        nonce = (graph.state_payload_json or {}).get("workflow_run_nonce")
        if not nonce or nonce != workflow_run_nonce:
            raise MemoryWriteForbidden("invalid_workflow_context_marker")
        if ledger.current_agent_role != agent_role:
            raise MemoryWriteForbidden("agent_role_mismatch")
        return directive, ledger, graph

    def write_from_graph(
        self,
        *,
        directive_id: uuid.UUID,
        task_ledger_id: uuid.UUID,
        agent_role: str,
        workflow_run_nonce: str,
        title: str | None,
        body: str,
        memory_kind: str,
        payload: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Called from LangGraph nodes only; enforces nonce + ledger alignment."""
        directive, ledger, _graph = self._validate_graph_context(
            directive_id=directive_id,
            task_ledger_id=task_ledger_id,
            agent_role=agent_role,
            workflow_run_nonce=workflow_run_nonce,
        )
        return self._persist(
            directive=directive,
            ledger_id=ledger.id,
            agent_role=agent_role,
            title=title,
            body=body,
            memory_kind=memory_kind,
            payload=payload or {},
        )

    def write_via_guarded_api(
        self,
        *,
        directive_id: uuid.UUID,
        task_ledger_id: uuid.UUID,
        agent_role: str,
        workflow_run_nonce: str,
        title: str | None,
        body: str,
        memory_kind: str,
        payload: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Same validation as graph path; REST must not bypass."""
        return self.write_from_graph(
            directive_id=directive_id,
            task_ledger_id=task_ledger_id,
            agent_role=agent_role,
            workflow_run_nonce=workflow_run_nonce,
            title=title,
            body=body,
            memory_kind=memory_kind,
            payload=payload,
        )

    def retry_vector_index_via_guarded_api(
        self,
        *,
        directive_id: uuid.UUID,
        task_ledger_id: uuid.UUID,
        agent_role: str,
        workflow_run_nonce: str,
        memory_entry_id: uuid.UUID,
    ) -> MemoryEntry:
        directive, _ledger, _graph = self._validate_graph_context(
            directive_id=directive_id,
            task_ledger_id=task_ledger_id,
            agent_role=agent_role,
            workflow_run_nonce=workflow_run_nonce,
        )
        row = self._session.get(MemoryEntry, memory_entry_id)
        if row is None:
            raise MemoryWriteForbidden("memory_entry_not_found")
        if row.directive_id != directive.id:
            raise MemoryWriteForbidden("memory_entry_directive_mismatch")
        return self._retry_vector_index(row, directive=directive)

    def _retry_vector_index(self, row: MemoryEntry, *, directive) -> MemoryEntry:
        """Re-attempt Chroma upsert; structured row stays authoritative."""
        row.vector_state = MemoryVectorState.VECTOR_PENDING.value
        row.vector_last_error = None
        self._session.flush()

        doc_id = str(row.id)
        try:
            self._vector.upsert_document(
                doc_id=doc_id,
                document=row.body_text,
                project_id=str(directive.project_id),
                directive_id=str(directive.id),
                memory_kind=row.memory_kind,
            )
            row.chroma_document_id = doc_id
            row.vector_state = MemoryVectorState.VECTOR_INDEXED.value
            row.vector_indexed_at = datetime.now(timezone.utc)
            row.vector_last_error = None
            self._session.flush()
            self._audit.record(
                event_type=AuditEventType.MEMORY_VECTOR_REINDEX_SUCCESS,
                event_payload={
                    "memory_entry_id": str(row.id),
                    "vector_state": row.vector_state,
                },
                actor_type=AuditActorType.SYSTEM,
                actor_id="memory:vector_retry",
                workspace_id=directive.workspace_id,
                project_id=directive.project_id,
                directive_id=directive.id,
            )
        except Exception as e:
            logger.warning("event=memory_vector_reindex_failed entry_id=%s err=%s", row.id, e)
            row.chroma_document_id = None
            row.vector_state = MemoryVectorState.VECTOR_FAILED.value
            row.vector_last_error = str(e)[:4000]
            row.vector_indexed_at = None
            self._session.flush()
            self._audit.record(
                event_type=AuditEventType.MEMORY_VECTOR_INDEX_FAILED,
                event_payload={
                    "memory_entry_id": str(row.id),
                    "phase": "retry",
                    "error": str(e)[:2000],
                },
                actor_type=AuditActorType.SYSTEM,
                actor_id="memory:vector_retry",
                workspace_id=directive.workspace_id,
                project_id=directive.project_id,
                directive_id=directive.id,
            )
        return row

    def _persist(
        self,
        *,
        directive,
        ledger_id: uuid.UUID,
        agent_role: str,
        title: str | None,
        body: str,
        memory_kind: str,
        payload: dict[str, Any],
    ) -> MemoryEntry:
        seq = allocate_memory_sequence(self._session)
        row = MemoryEntry(
            directive_id=directive.id,
            project_id=directive.project_id,
            task_ledger_id=ledger_id,
            agent_role=agent_role,
            memory_kind=memory_kind,
            title=title,
            body_text=body,
            payload_json=payload,
            chroma_document_id=None,
            memory_sequence=seq,
            vector_state=MemoryVectorState.STRUCTURED_COMMITTED.value,
            vector_last_error=None,
            vector_indexed_at=None,
        )
        self._session.add(row)
        self._session.flush()

        row.vector_state = MemoryVectorState.VECTOR_PENDING.value
        self._session.flush()

        doc_id = str(row.id)
        try:
            self._vector.upsert_document(
                doc_id=doc_id,
                document=body,
                project_id=str(directive.project_id),
                directive_id=str(directive.id),
                memory_kind=memory_kind,
            )
            row.chroma_document_id = doc_id
            row.vector_state = MemoryVectorState.VECTOR_INDEXED.value
            row.vector_indexed_at = datetime.now(timezone.utc)
            row.vector_last_error = None
        except Exception as e:
            logger.warning("event=memory_vector_index_failed entry_id=%s err=%s", row.id, e)
            row.chroma_document_id = None
            row.vector_state = MemoryVectorState.VECTOR_FAILED.value
            row.vector_last_error = str(e)[:4000]
            row.vector_indexed_at = None
            self._audit.record(
                event_type=AuditEventType.MEMORY_VECTOR_INDEX_FAILED,
                event_payload={
                    "memory_entry_id": str(row.id),
                    "phase": "initial",
                    "error": str(e)[:2000],
                },
                actor_type=AuditActorType.SYSTEM,
                actor_id="memory:vector_index",
                workspace_id=directive.workspace_id,
                project_id=directive.project_id,
                directive_id=directive.id,
            )

        self._session.flush()

        self._audit.record(
            event_type=AuditEventType.MEMORY_WRITE,
            event_payload={
                "memory_entry_id": str(row.id),
                "memory_kind": memory_kind,
                "memory_sequence": seq,
                "vector_state": row.vector_state,
                "title": title,
                "task_ledger_id": str(ledger_id),
                "agent_role": agent_role,
            },
            actor_type=AuditActorType.AGENT,
            actor_id=f"memory:{agent_role}",
            workspace_id=directive.workspace_id,
            project_id=directive.project_id,
            directive_id=directive.id,
        )
        return row
