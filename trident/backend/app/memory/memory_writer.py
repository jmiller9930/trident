"""Graph-governed memory writes + audit (100D)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import Settings, settings as app_settings
from app.models.enums import AuditActorType, AuditEventType, TaskLifecycleState
from app.models.memory_entry import MemoryEntry
from app.repositories.audit_repository import AuditRepository
from app.workflow.persistence import load_spine_context

from app.memory.exceptions import MemoryWriteForbidden
from app.memory.vector_service import VectorMemoryService


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
        )
        self._session.add(row)
        self._session.flush()

        doc_id = str(row.id)
        self._vector.upsert_document(
            doc_id=doc_id,
            document=body,
            project_id=str(directive.project_id),
            directive_id=str(directive.id),
            memory_kind=memory_kind,
        )
        row.chroma_document_id = doc_id
        self._session.flush()

        self._audit.record(
            event_type=AuditEventType.MEMORY_WRITE,
            event_payload={
                "memory_entry_id": str(row.id),
                "memory_kind": memory_kind,
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
