"""Intent → subsystem route classification (100G). Deterministic; fail closed on ambiguity."""

from __future__ import annotations

from enum import StrEnum


class RouterRoute(StrEnum):
    MCP = "MCP"
    LANGGRAPH = "LANGGRAPH"
    NIKE = "NIKE"
    MEMORY = "MEMORY"


def classify_intent(intent: str) -> tuple[RouterRoute | None, str]:
    """
    Rules (deterministic):
    - Optional explicit prefix `route.<segment>` where segment ∈ memory|mcp|langgraph|nike.
    - Otherwise keyword tokens (substring match). Multiple subsystem signals → ambiguous.
    """
    raw = intent.strip()
    if not raw:
        return None, "empty_intent"

    key = raw.lower()

    if key.startswith("route."):
        seg = key.removeprefix("route.").split(".", 1)[0].strip()
        mapping = {
            "memory": RouterRoute.MEMORY,
            "mcp": RouterRoute.MCP,
            "langgraph": RouterRoute.LANGGRAPH,
            "nike": RouterRoute.NIKE,
        }
        if seg in mapping:
            return mapping[seg], f"explicit_route.{seg}"
        return None, "unknown_route_prefix"

    signals: list[RouterRoute] = []

    memory_markers = ("memory_read", "knowledge_read", "scoped_retrieval", "vector_context")
    mcp_markers = ("mcp_execute", "command_execution", "tool_execution_path")
    lg_markers = ("workflow_progress", "graph_continue", "ledger_transition")
    nike_markers = ("nike_dispatch", "event_coordination", "orchestration_emit")

    if any(m in key for m in memory_markers):
        signals.append(RouterRoute.MEMORY)
    if any(m in key for m in mcp_markers):
        signals.append(RouterRoute.MCP)
    if any(m in key for m in lg_markers):
        signals.append(RouterRoute.LANGGRAPH)
    if any(m in key for m in nike_markers):
        signals.append(RouterRoute.NIKE)

    seen: list[RouterRoute] = []
    for s in signals:
        if s not in seen:
            seen.append(s)

    if len(seen) == 0:
        return None, "no_subsystem_match"
    if len(seen) > 1:
        return None, "ambiguous_multi_subsystem"
    return seen[0], "keyword_match"


def next_action_hint(route: RouterRoute) -> str:
    """Static caller hint only — router does not invoke these paths."""
    return {
        RouterRoute.MCP: "POST /api/v1/mcp/classify then POST /api/v1/mcp/execute",
        RouterRoute.LANGGRAPH: "POST /api/v1/directives/{directive_id}/workflow/run",
        RouterRoute.NIKE: "POST /api/v1/nike/events",
        RouterRoute.MEMORY: "GET /api/v1/memory/directive/{directive_id}",
    }[route]
