"""Controlled external stub — no live HTTP by default (100R fallback path)."""

from __future__ import annotations


def external_complete_stub(*, optimized_prompt: str, external_model_id: str) -> str:
    """Returns deterministic payload — swap for real adapter only under governed ops."""
    return (
        f"[external:{external_model_id}] stub_exec "
        f"optimized_input_chars={len(optimized_prompt)}"
    )

