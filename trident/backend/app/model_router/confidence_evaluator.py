"""FIX 005 §5 — pluggable confidence calibration (default deterministic signals)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.config.settings import Settings


@dataclass(frozen=True)
class ConfidenceEvaluation:
    confidence: float
    signals: dict[str, Any]


class ConfidenceEvaluator(Protocol):
    def evaluate(
        self,
        *,
        raw_local_confidence: float,
        prompt: str,
        local_adapter_meta: dict[str, Any],
        settings: Settings,
    ) -> ConfidenceEvaluation:
        ...


class DefaultConfidenceEvaluator:
    """Deterministic blend of adapter score + prompt/meta signals (CI-safe)."""

    def evaluate(
        self,
        *,
        raw_local_confidence: float,
        prompt: str,
        local_adapter_meta: dict[str, Any],
        settings: Settings,
    ) -> ConfidenceEvaluation:
        signals: dict[str, Any] = {
            "adapter_raw_confidence": raw_local_confidence,
            "prompt_char_len": len(prompt),
            "local_adapter_meta": dict(local_adapter_meta),
        }
        conf = float(raw_local_confidence)

        if local_adapter_meta.get("incomplete"):
            conf = min(conf, 0.42)
            signals["signal_incomplete_local_response"] = True

        if "[PARSE_FAILURE]" in prompt.upper():
            conf = min(conf, 0.38)
            signals["signal_parse_failure_marker"] = True

        if "[TEST_FAILURE_LOCAL]" in prompt.upper():
            conf = min(conf, 0.33)
            signals["signal_test_failure_after_local"] = True

        soft = settings.model_router_context_soft_limit_chars
        if soft > 0 and len(prompt) > soft:
            conf = min(conf, 0.28)
            signals["signal_context_over_soft_limit"] = True

        conf = max(0.0, min(1.0, conf))
        signals["final_calibrated_confidence"] = conf
        return ConfidenceEvaluation(confidence=conf, signals=signals)
