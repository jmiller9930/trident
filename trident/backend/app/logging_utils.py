"""Shared logging tweaks for API and worker (100L — reduce dependency noise)."""

from __future__ import annotations

import logging


def configure_dependency_log_levels(root_level: int) -> None:
    """When root is INFO or higher, keep chatty HTTP/Chroma/PG libraries at WARNING+."""
    if root_level <= logging.DEBUG:
        return
    floor = max(logging.WARNING, root_level)
    for name in (
        "chromadb",
        "chromadb.telemetry",
        "chromadb.telemetry.product.posthog",
        "httpx",
        "httpcore",
    ):
        logging.getLogger(name).setLevel(floor)
