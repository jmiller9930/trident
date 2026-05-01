"""Runs agent handlers and applies MCP + memory **only** through sanctioned services."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.agent_context import AgentGraphContext
from app.agents.agent_logger import AgentAuditLogger
from app.agents.agent_registry import resolve_handler
from app.agents.schemas import AgentDecisionStatus, AgentOutput
from app.config.settings import Settings
from app.memory.memory_reader import MemoryReader
from app.memory.memory_writer import MemoryWriter
from app.mcp.mcp_service import MCPService
from app.models.directive import Directive
from app.models.enums import AgentRole
from app.models.graph_state import GraphState
from app.models.task_ledger import TaskLedger
from app.model_router.langgraph_hook import invoke_model_router_for_engineer_node
from app.schemas.mcp import MCPExecuteRequest
from app.workflow.state import SpineState


class AgentExecutor:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._mcp = MCPService(session)
        self._memory = MemoryWriter(session)
        self._agents = AgentAuditLogger(session)
        self._reader = MemoryReader(session)

    def run(
        self,
        *,
        directive: Directive,
        ledger: TaskLedger,
        _graph: GraphState,
        state: SpineState,
        node_name: str,
        role: AgentRole,
        model_routing_trace: dict[str, Any] | None = None,
    ) -> AgentOutput:
        handler = resolve_handler(role)
        if handler is None:
            return AgentOutput(decision="noop: no handler for role", status=AgentDecisionStatus.CONTINUE)

        snap = self._reader.read_directive(directive.id)
        ctx = AgentGraphContext(
            directive_id=directive.id,
            task_ledger_id=ledger.id,
            workflow_run_nonce=state["workflow_run_nonce"],
            agent_role=role,
            node_name=node_name,
            memory_snapshot=snap if isinstance(snap, dict) else {"snapshot": snap},
            model_routing=model_routing_trace,
        )

        self._agents.invocation(directive=directive, ledger=ledger, node_name=node_name, role=role)

        out = handler(self._session, ctx)
        self._agents.decision(
            directive=directive,
            ledger=ledger,
            node_name=node_name,
            payload={
                "decision": out.decision,
                "status": out.status.value,
                "has_mcp": out.mcp_request is not None,
                "has_memory_write": out.memory_write is not None,
            },
        )

        mcp_proof_id = None
        if out.mcp_request:
            self._agents.mcp_request(
                directive=directive,
                ledger=ledger,
                node_name=node_name,
                command=out.mcp_request.command,
                target=out.mcp_request.target,
                explicitly_approved=out.mcp_request.explicitly_approved,
            )
            resp = self._mcp.execute(
                MCPExecuteRequest(
                    directive_id=directive.id,
                    task_id=ledger.id,
                    agent_role=ledger.current_agent_role,
                    command=out.mcp_request.command,
                    target=out.mcp_request.target,
                    explicitly_approved=out.mcp_request.explicitly_approved,
                )
            )
            mcp_proof_id = str(resp.proof_object_id)

        memory_written = False
        if out.memory_write:
            self._memory.write_from_graph(
                directive_id=directive.id,
                task_ledger_id=ledger.id,
                agent_role=ledger.current_agent_role,
                workflow_run_nonce=state["workflow_run_nonce"],
                title=out.memory_write.title,
                body=out.memory_write.body,
                memory_kind=out.memory_write.memory_kind,
            )
            memory_written = True

        self._agents.result(
            directive=directive,
            ledger=ledger,
            node_name=node_name,
            payload={
                "mcp_proof_object_id": mcp_proof_id,
                "memory_written": memory_written,
                "agent_status": out.status.value,
            },
        )
        return out


def run_engineer_agent_phase(
    session: Session,
    directive: Directive,
    ledger: TaskLedger,
    graph: GraphState,
    state: SpineState,
    *,
    model_router_settings: Settings | None = None,
) -> AgentOutput:
    trace = invoke_model_router_for_engineer_node(
        session,
        directive=directive,
        ledger=ledger,
        state=state,
        settings=model_router_settings,
    )
    return AgentExecutor(session).run(
        directive=directive,
        ledger=ledger,
        _graph=graph,
        state=state,
        node_name="engineer",
        role=AgentRole.ENGINEER,
        model_routing_trace=trace,
    )
