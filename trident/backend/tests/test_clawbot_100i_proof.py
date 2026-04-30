"""100I clawbot proof — ordered audit subsequence (router + agent + MCP chain)."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.enums import AuditEventType
from clawbot_100i_proof import find_100i_audit_ordered_subsequence, memory_sequence_monotonic


def test_100i_subsequence_accepts_interleaved_audits() -> None:
    types = [
        AuditEventType.DIRECTIVE_CREATED.value,
        AuditEventType.STATE_TRANSITION.value,
        AuditEventType.ROUTER_DECISION_MADE.value,
        AuditEventType.MEMORY_READ_ACCESS.value,
        AuditEventType.AGENT_INVOCATION.value,
        AuditEventType.AGENT_DECISION.value,
        AuditEventType.AGENT_MCP_REQUEST.value,
        AuditEventType.MCP_EXECUTION_REQUESTED.value,
        AuditEventType.MCP_EXECUTION_COMPLETED.value,
        AuditEventType.MEMORY_WRITE.value,
        AuditEventType.AGENT_RESULT.value,
    ]
    assert find_100i_audit_ordered_subsequence(types)


def test_100i_subsequence_rejects_missing_router() -> None:
    types = [
        AuditEventType.AGENT_INVOCATION.value,
        AuditEventType.AGENT_DECISION.value,
        AuditEventType.AGENT_MCP_REQUEST.value,
        AuditEventType.MCP_EXECUTION_REQUESTED.value,
        AuditEventType.MCP_EXECUTION_COMPLETED.value,
        AuditEventType.MEMORY_WRITE.value,
        AuditEventType.AGENT_RESULT.value,
    ]
    assert not find_100i_audit_ordered_subsequence(types)


def test_memory_sequence_monotonic_accepts_non_decreasing() -> None:
    rows = [
        SimpleNamespace(memory_sequence=1),
        SimpleNamespace(memory_sequence=2),
        SimpleNamespace(memory_sequence=2),
    ]
    assert memory_sequence_monotonic(rows)


def test_memory_sequence_monotonic_rejects_decrease() -> None:
    rows = [
        SimpleNamespace(memory_sequence=2),
        SimpleNamespace(memory_sequence=1),
    ]
    assert not memory_sequence_monotonic(rows)


def test_100i_subsequence_rejects_wrong_order() -> None:
    types = [
        AuditEventType.ROUTER_DECISION_MADE.value,
        AuditEventType.AGENT_INVOCATION.value,
        AuditEventType.MEMORY_WRITE.value,
        AuditEventType.AGENT_DECISION.value,
    ]
    assert not find_100i_audit_ordered_subsequence(types)
