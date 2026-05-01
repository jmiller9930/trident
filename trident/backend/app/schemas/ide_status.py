"""IDE_002 — proof-summary and status read endpoints for extension polling."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class IdeStatusResponse(BaseModel):
    """Lightweight directive + ledger snapshot for extension status polling (IDE_002)."""

    directive_id: uuid.UUID
    title: str
    directive_status: str
    ledger_state: str
    current_agent_role: str
    last_routing_decision: dict[str, Any] | None = None
    last_routing_model: str | None = None
    nodes_executed: list[str] | None = None


class IdeProofSummaryResponse(BaseModel):
    """Audit + proof snapshot for the extension proof panel (IDE_002)."""

    directive_id: uuid.UUID
    title: str
    directive_status: str
    ledger_state: str
    current_agent_role: str
    proof_count: int
    last_routing_decision: dict[str, Any] | None = None
    last_routing_model: str | None = None
    last_mcp_events: list[dict[str, Any]]
    last_patch_event: dict[str, Any] | None = None
