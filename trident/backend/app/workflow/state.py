"""LangGraph spine state model (100C)."""

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict


class SpineState(TypedDict):
    """State carried through the default Trident delivery graph."""

    directive_id: str
    workflow_run_nonce: str
    reviewer_rejections_remaining: int
    reviewer_send_back: bool
    nodes_executed: Annotated[list[str], add]
