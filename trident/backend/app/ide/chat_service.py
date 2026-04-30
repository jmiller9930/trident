"""Deterministic IDE chat stub — audits + CHAT_LOG proof (100K)."""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy.orm import Session

from app.models.enums import AgentRole, AuditActorType, AuditEventType, ProofObjectType
from app.models.proof_object import ProofObject
from app.repositories.audit_repository import AuditRepository
from app.repositories.directive_repository import DirectiveRepository

MAX_PROMPT_LEN = 16_384


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stub_reply(correlation_id: uuid.UUID, prompt_sha256: str) -> str:
    return (
        "Trident IDE chat (deterministic stub; no LLM). "
        f"correlation_id={correlation_id}; prompt_sha256_prefix={prompt_sha256[:16]}"
    )


def process_ide_chat(
    session: Session,
    *,
    directive_id: uuid.UUID,
    prompt: str,
    actor_id: str | None,
) -> tuple[str, uuid.UUID, uuid.UUID]:
    raw = prompt.strip()
    if not raw:
        raise ValueError("prompt_empty")
    if len(raw) > MAX_PROMPT_LEN:
        raise ValueError("prompt_too_long")

    d = DirectiveRepository(session).get_by_id(directive_id)
    if d is None:
        raise ValueError("directive_not_found")

    correlation_id = uuid.uuid4()
    prompt_sha = _sha256_hex(raw)
    audit = AuditRepository(session)

    audit.record(
        event_type=AuditEventType.IDE_CHAT_REQUEST,
        event_payload={
            "correlation_id": str(correlation_id),
            "directive_id": str(directive_id),
            "prompt_sha256": prompt_sha,
            "prompt_length": len(raw),
        },
        actor_type=AuditActorType.USER,
        actor_id=actor_id or "ide-client",
        workspace_id=d.workspace_id,
        project_id=d.project_id,
        directive_id=directive_id,
    )
    session.flush()

    reply = _stub_reply(correlation_id, prompt_sha)
    reply_sha = _sha256_hex(reply)
    proof_summary = json.dumps(
        {
            "schema": "ide_chat_stub_v1",
            "correlation_id": str(correlation_id),
            "prompt_sha256": prompt_sha,
            "reply_sha256": reply_sha,
        }
    )
    proof = ProofObject(
        directive_id=directive_id,
        proof_type=ProofObjectType.CHAT_LOG.value,
        proof_summary=proof_summary,
        proof_uri=None,
        proof_hash=reply_sha,
        created_by_agent_role=AgentRole.USER.value,
    )
    session.add(proof)
    session.flush()

    audit.record(
        event_type=AuditEventType.IDE_CHAT_RESPONSE,
        event_payload={
            "correlation_id": str(correlation_id),
            "directive_id": str(directive_id),
            "reply_sha256": reply_sha,
            "proof_object_id": str(proof.id),
        },
        actor_type=AuditActorType.SYSTEM,
        actor_id="trident-api",
        workspace_id=d.workspace_id,
        project_id=d.project_id,
        directive_id=directive_id,
    )

    return reply, correlation_id, proof.id
