"""FIX 005 — in-memory external usage per directive + audit-backed warnings."""

from __future__ import annotations

import threading
import uuid
from collections import defaultdict

_lock = threading.Lock()
_usage_chars_by_directive: dict[uuid.UUID, int] = defaultdict(int)


def reset_budget_counters() -> None:
    """Test helper — clears in-memory counters."""
    with _lock:
        _usage_chars_by_directive.clear()


def get_external_usage_chars(directive_id: uuid.UUID) -> int:
    with _lock:
        return int(_usage_chars_by_directive.get(directive_id, 0))


def add_external_usage_chars(directive_id: uuid.UUID, n: int) -> int:
    if n <= 0:
        return get_external_usage_chars(directive_id)
    with _lock:
        _usage_chars_by_directive[directive_id] += n
        return int(_usage_chars_by_directive[directive_id])


def snapshot_usage_all() -> dict[str, int]:
    with _lock:
        return {str(k): int(v) for k, v in _usage_chars_by_directive.items()}
