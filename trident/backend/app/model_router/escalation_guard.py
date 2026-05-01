"""FIX 005 — central escalation proposal from calibrated confidence + markers."""

from __future__ import annotations

from typing import Any

from app.config.settings import Settings
from app.model_router.reason_codes import Fix005EscalationReason


def propose_escalation_reason(
    *,
    calibrated_confidence: float,
    prompt: str,
    local_adapter_meta: dict[str, Any],
    settings: Settings,
) -> Fix005EscalationReason | None:
    """
    Returns the primary FIX 005 escalation trigger if external path should be considered.
    Priority follows directive §4 / §5 (deterministic markers for CI).
    """
    upper = prompt.upper()

    if "[USER_APPROVED_EXTERNAL]" in upper or "[USER_APPROVED_ESCALATION]" in upper:
        return Fix005EscalationReason.USER_APPROVED_ESCALATION
    if "[EXT_REQUIRED]" in prompt:
        return Fix005EscalationReason.VALIDATION_REQUIRED
    if "[LOCAL_UNAVAILABLE]" in upper:
        return Fix005EscalationReason.LOCAL_MODEL_UNAVAILABLE

    soft = settings.model_router_context_soft_limit_chars
    if soft > 0 and len(prompt) > soft:
        return Fix005EscalationReason.CONTEXT_WINDOW_LIMIT

    if "HIGH_REASONING" in upper:
        return Fix005EscalationReason.HIGH_REASONING_REQUIRED

    if local_adapter_meta.get("incomplete") or "[INCOMPLETE]" in upper:
        return Fix005EscalationReason.INCOMPLETE_RESPONSE

    if calibrated_confidence < settings.model_router_escalation_confidence_threshold:
        return Fix005EscalationReason.LOW_CONFIDENCE

    return None
