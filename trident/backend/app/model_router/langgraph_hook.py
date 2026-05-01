"""Single LangGraph call site for 100R — engineer node only."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import Settings, settings as app_settings
from app.model_router.model_router_service import ModelRouterService
from app.models.directive import Directive
from app.models.enums import AgentRole
from app.models.task_ledger import TaskLedger
from app.workflow.state import SpineState


def _compose_router_prompt(directive: Directive, ledger: TaskLedger, state: SpineState) -> str:
    return (
        f"directive_id={directive.id}\n"
        f"title={directive.title}\n"
        f"task_ledger_id={ledger.id}\n"
        f"workflow_run_nonce={state['workflow_run_nonce']}\n"
        f"graph_agent_role={ledger.current_agent_role}"
    )


def invoke_model_router_for_engineer_node(
    session: Session,
    *,
    directive: Directive,
    ledger: TaskLedger,
    state: SpineState,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Invoked only from LangGraph-governed engineer phase (100R §10).
    Not callable from IDE / MCP / Nike.
    """
    cfg = settings if settings is not None else app_settings
    prompt = _compose_router_prompt(directive, ledger, state)
    svc = ModelRouterService(session, cfg)
    result = svc.route(
        directive=directive,
        ledger=ledger,
        agent_role=AgentRole.ENGINEER,
        prompt=prompt,
    )
    return {
        **result.as_trace_dict(),
        "full_response_chars": len(result.response_text),
        "optimized_prompt_chars": len(result.optimized_prompt or ""),
    }

