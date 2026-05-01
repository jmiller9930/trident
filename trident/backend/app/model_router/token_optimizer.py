"""100R §8 — trim/summarize context before external escalation."""

from __future__ import annotations


def optimize_prompt_for_external(prompt: str, *, max_chars: int) -> tuple[str, dict[str, int | bool]]:
    if len(prompt) <= max_chars:
        return prompt, {"trimmed": False, "original_chars": len(prompt), "optimized_chars": len(prompt)}
    trimmed = prompt[:max_chars].rstrip()
    return trimmed + "\n…[trident_token_optimizer_truncated]", {
        "trimmed": True,
        "original_chars": len(prompt),
        "optimized_chars": len(trimmed) + 36,
    }

