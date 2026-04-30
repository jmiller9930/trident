from __future__ import annotations

import uuid

from pydantic import BaseModel


class WorkflowRunResponse(BaseModel):
    directive_id: uuid.UUID
    final_ledger_state: str
    directive_status: str
    nodes_executed: list[str]
