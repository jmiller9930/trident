"""Deterministic agent stubs — replace with model-backed handlers when in scope."""

from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.agents.agent_context import AgentGraphContext
from app.agents.schemas import AgentDecisionStatus, AgentMCPIntent, AgentMemoryWriteIntent, AgentOutput
from app.memory.constants import MemoryKind
from app.models.enums import AgentRole

AgentHandler = Callable[[Session, AgentGraphContext], AgentOutput]


def _engineer_stub(_session: Session, ctx: AgentGraphContext) -> AgentOutput:
    # LOW-risk MCP path (pytest prefix); execution still goes through MCPService only.
    return AgentOutput(
        decision="Proceed per engineer stub (100H governed path)",
        status=AgentDecisionStatus.CONTINUE,
        mcp_request=AgentMCPIntent(
            command="pytest trident_force_low agent_100h_stub",
            target="local",
            explicitly_approved=True,
        ),
        memory_write=AgentMemoryWriteIntent(
            title="agent:engineer",
            body=f"100H agent checkpoint directive={ctx.directive_id} node={ctx.node_name}",
            memory_kind=MemoryKind.STRUCTURED.value,
        ),
    )


def resolve_handler(role: AgentRole) -> AgentHandler | None:
    if role == AgentRole.ENGINEER:
        return _engineer_stub
    return None
