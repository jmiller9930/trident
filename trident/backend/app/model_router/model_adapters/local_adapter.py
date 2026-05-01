"""Deterministic local LLM stub — returns text + confidence + meta (100R / FIX 005)."""

from __future__ import annotations

from typing import Any


def local_complete(*, prompt: str, profile_id: str) -> tuple[str, float, dict[str, Any]]:
    """
    Deterministic: HIGHCONF unless prompt contains LOWCONF (tests) or HIGH_REASONING marker.
    """
    base = f"[local:{profile_id}] synthesized_stub directive_context_chars={len(prompt)}"
    upper = prompt.upper()
    meta: dict[str, Any] = {"incomplete": False, "self_rating_stub": 0.92}

    if "LOWCONF" in upper:
        meta["self_rating_stub"] = 0.18
        return base, 0.18, meta

    if "HIGH_REASONING" in upper:
        meta["self_rating_stub"] = 0.35
        return base + " (reasoning-heavy stub)", 0.35, meta

    if "[LOCAL_UNAVAILABLE]" in upper:
        meta["adapter_reported_unavailable"] = True
        return base + " (unavailable stub)", 0.0, meta

    if "INCOMPLETE" in upper:
        meta["incomplete"] = True
        meta["self_rating_stub"] = 0.55
        return base + " (incomplete stub)", 0.55, meta

    return base, 0.92, meta
