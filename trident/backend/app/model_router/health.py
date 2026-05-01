"""Benchmark / health hooks — pure Python; no new public HTTP surface required."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.model_router.model_router_logger import log_benchmark_hook
from app.model_router.registry import resolve_profile_id
from app.models.directive import Directive
from app.models.enums import AgentRole
from app.models.task_ledger import TaskLedger


def model_router_health_snapshot(*, settings: Settings, agent_role: AgentRole = AgentRole.ENGINEER) -> dict[str, Any]:
    profile = resolve_profile_id(agent_role=agent_role, settings=settings)
    return {
        "mode": settings.model_router_mode,
        "escalation_enabled": settings.model_router_escalation_enabled,
        "threshold": settings.model_router_escalation_confidence_threshold,
        "resolved_profile_engineer": profile,
        "token_budget_chars": settings.model_router_token_budget_chars,
        "external_budget_max_chars": settings.model_router_external_budget_max_chars,
        "external_budget_warn_ratio": settings.model_router_external_budget_warn_ratio,
        "context_soft_limit_chars": settings.model_router_context_soft_limit_chars,
    }


def trigger_benchmark_audit(
    session: Session,
    *,
    directive: Directive,
    ledger: TaskLedger,
    settings: Settings,
) -> None:
    """Optional hook for synthetic VRAM/latency placeholders — emits MODEL_ROUTER_BENCHMARK."""
    snap = model_router_health_snapshot(settings=settings)
    log_benchmark_hook(
        session,
        directive=directive,
        ledger=ledger,
        metrics={"health_snapshot": snap, "note": "benchmark_placeholder_v1"},
    )
