"""100R / FIX 005 — model routing core with calibrated confidence + guard + budget."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.model_router.budget import add_external_usage_chars, get_external_usage_chars
from app.model_router.confidence_evaluator import ConfidenceEvaluator, DefaultConfidenceEvaluator
from app.model_router.escalation_guard import propose_escalation_reason
from app.model_router.model_adapters.external_adapter import external_complete_stub
from app.model_router.model_adapters.local_adapter import local_complete
from app.model_router.model_router_logger import log_budget_warning, log_routing_decision
from app.model_router.reason_codes import Fix005BlockReason, Fix005EscalationReason, Fix005LocalOutcome
from app.model_router.registry import resolve_external_model_id, resolve_profile_id
from app.model_router.token_optimizer import optimize_prompt_for_external
from app.models.directive import Directive
from app.models.enums import AgentRole
from app.models.task_ledger import TaskLedger
from app.services.model_router import (
    ModelPlaneHttpRoute,
    ModelPlaneRequestType,
    ModelPlaneRouterService,
    ModelPlaneUnavailableError,
)


def _ollama_chat_response_text(body: dict[str, Any]) -> str:
    msg = body.get("message")
    if isinstance(msg, dict) and msg.get("content") is not None:
        return str(msg["content"])
    if body.get("response") is not None:
        return str(body["response"])
    return ""


@dataclass(frozen=True)
class ModelRouterResult:
    decision: Literal["LOCAL", "EXTERNAL"]
    primary_audit_code: str
    escalation_trigger_code: str | None
    blocked_external: bool
    blocked_reason_code: str | None
    calibrated_confidence: float
    local_adapter_raw_confidence: float
    signal_breakdown: dict[str, Any]
    token_optimization: dict[str, Any]
    response_text: str
    local_model_profile_id: str
    external_model_id: str | None
    optimized_prompt: str | None

    @property
    def reason(self) -> str:
        """Backward compat for tests — mirrors primary_audit_code."""
        return self.primary_audit_code

    @property
    def local_confidence(self) -> float:
        return self.calibrated_confidence

    def as_trace_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "primary_audit_code": self.primary_audit_code,
            "escalation_trigger_code": self.escalation_trigger_code,
            "blocked_external": self.blocked_external,
            "blocked_reason_code": self.blocked_reason_code,
            "calibrated_confidence": self.calibrated_confidence,
            "local_adapter_raw_confidence": self.local_adapter_raw_confidence,
            "signal_breakdown": self.signal_breakdown,
            "token_optimization": self.token_optimization,
            "response_preview": self.response_text[:500],
            "local_model_profile_id": self.local_model_profile_id,
            "external_model_id": self.external_model_id,
        }


class ModelRouterService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        confidence_evaluator: ConfidenceEvaluator | None = None,
        model_plane_router: ModelPlaneRouterService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._conf_eval: ConfidenceEvaluator = confidence_evaluator or DefaultConfidenceEvaluator()
        self._model_plane_router = model_plane_router

    def route(
        self,
        *,
        directive: Directive,
        ledger: TaskLedger,
        agent_role: AgentRole,
        prompt: str,
    ) -> ModelRouterResult:
        profile_id = resolve_profile_id(agent_role=agent_role, settings=self._settings)
        local_text, raw_conf, local_meta = local_complete(prompt=prompt, profile_id=profile_id)
        ce = self._conf_eval.evaluate(
            raw_local_confidence=raw_conf,
            prompt=prompt,
            local_adapter_meta=local_meta,
            settings=self._settings,
        )

        proposed = propose_escalation_reason(
            calibrated_confidence=ce.confidence,
            prompt=prompt,
            local_adapter_meta=local_meta,
            settings=self._settings,
        )

        escalation_code = proposed.value if proposed else None

        if proposed is None:
            tok = {"external_path_skipped": True, "note": "no_escalation_trigger"}
            payload = self._payload_base(
                directive=directive,
                ledger=ledger,
                profile_id=profile_id,
                routing_outcome="LOCAL",
                escalation_code=None,
                blocked_external=False,
                blocked_code=None,
                primary=Fix005LocalOutcome.LOCAL_COMPLETED.value,
                calibrated=ce.confidence,
                raw_conf=raw_conf,
                signals=ce.signals,
                token_meta=tok,
                external_id=None,
            )
            log_routing_decision(self._session, directive=directive, ledger=ledger, payload=payload)
            return ModelRouterResult(
                decision="LOCAL",
                primary_audit_code=Fix005LocalOutcome.LOCAL_COMPLETED.value,
                escalation_trigger_code=None,
                blocked_external=False,
                blocked_reason_code=None,
                calibrated_confidence=ce.confidence,
                local_adapter_raw_confidence=raw_conf,
                signal_breakdown=ce.signals,
                token_optimization=tok,
                response_text=local_text,
                local_model_profile_id=profile_id,
                external_model_id=None,
                optimized_prompt=None,
            )

        if not self._settings.model_router_escalation_enabled:
            tok = {
                "external_path_skipped": True,
                "would_escalate_trigger": escalation_code,
                "policy": Fix005BlockReason.EXTERNAL_ESCALATION_DISABLED.value,
            }
            primary = Fix005BlockReason.EXTERNAL_ESCALATION_DISABLED.value
            payload = self._payload_base(
                directive=directive,
                ledger=ledger,
                profile_id=profile_id,
                routing_outcome="LOCAL",
                escalation_code=escalation_code,
                blocked_external=True,
                blocked_code=primary,
                primary=primary,
                calibrated=ce.confidence,
                raw_conf=raw_conf,
                signals=ce.signals,
                token_meta=tok,
                external_id=None,
            )
            log_routing_decision(self._session, directive=directive, ledger=ledger, payload=payload)
            return ModelRouterResult(
                decision="LOCAL",
                primary_audit_code=primary,
                escalation_trigger_code=escalation_code,
                blocked_external=True,
                blocked_reason_code=primary,
                calibrated_confidence=ce.confidence,
                local_adapter_raw_confidence=raw_conf,
                signal_breakdown=ce.signals,
                token_optimization=tok,
                response_text=local_text,
                local_model_profile_id=profile_id,
                external_model_id=None,
                optimized_prompt=None,
            )

        optimized, opt_meta = optimize_prompt_for_external(
            prompt, max_chars=self._settings.model_router_token_budget_chars
        )
        est_chars = len(optimized)
        usage_before = get_external_usage_chars(directive.id)
        max_b = self._settings.model_router_external_budget_max_chars

        if max_b > 0 and usage_before + est_chars > max_b:
            tok = {
                "external_path_skipped": True,
                "would_escalate_trigger": escalation_code,
                "budget_usage_before": usage_before,
                "budget_limit": max_b,
                "estimated_external_chars": est_chars,
                "token_optimizer_meta": opt_meta,
            }
            br = Fix005BlockReason.BUDGET_EXCEEDED.value
            payload = self._payload_base(
                directive=directive,
                ledger=ledger,
                profile_id=profile_id,
                routing_outcome="LOCAL",
                escalation_code=escalation_code,
                blocked_external=True,
                blocked_code=br,
                primary=br,
                calibrated=ce.confidence,
                raw_conf=raw_conf,
                signals=ce.signals,
                token_meta=tok,
                external_id=None,
            )
            log_routing_decision(self._session, directive=directive, ledger=ledger, payload=payload)
            return ModelRouterResult(
                decision="LOCAL",
                primary_audit_code=br,
                escalation_trigger_code=escalation_code,
                blocked_external=True,
                blocked_reason_code=br,
                calibrated_confidence=ce.confidence,
                local_adapter_raw_confidence=raw_conf,
                signal_breakdown=ce.signals,
                token_optimization=tok,
                response_text=local_text,
                local_model_profile_id=profile_id,
                external_model_id=None,
                optimized_prompt=optimized,
            )

        external_id = resolve_external_model_id(agent_role=agent_role, settings=self._settings)
        correlation_id: uuid.UUID | None = None
        used_model_plane = False

        if self._settings.engineer_use_model_plane:
            correlation_id = uuid.uuid4()
            used_model_plane = True
            try:
                plane = self._model_plane_router or ModelPlaneRouterService.get_or_create(self._settings)
                raw = plane.call_model(
                    ModelPlaneHttpRoute.CHAT,
                    {
                        "model": external_id,
                        "messages": [{"role": "user", "content": optimized}],
                        "stream": False,
                    },
                    request_type=ModelPlaneRequestType.CHAT,
                    prefer_secondary=self._settings.engineer_model_plane_prefer_secondary,
                    session=self._session,
                    directive_id=directive.id,
                    project_id=directive.project_id,
                    workspace_id=directive.workspace_id,
                    correlation_id=correlation_id,
                )
                final_text = _ollama_chat_response_text(raw)
            except ModelPlaneUnavailableError as e:
                tok = {
                    **opt_meta,
                    "external_path_skipped": True,
                    "would_escalate_trigger": escalation_code,
                    "model_plane_correlation_id": str(correlation_id),
                    "model_plane_error": e.as_dict(),
                }
                br = Fix005BlockReason.MODEL_PLANE_UNAVAILABLE.value
                payload = self._payload_base(
                    directive=directive,
                    ledger=ledger,
                    profile_id=profile_id,
                    routing_outcome="LOCAL",
                    escalation_code=escalation_code,
                    blocked_external=True,
                    blocked_code=br,
                    primary=br,
                    calibrated=ce.confidence,
                    raw_conf=raw_conf,
                    signals=ce.signals,
                    token_meta=tok,
                    external_id=external_id,
                )
                payload["model_plane_correlation_id"] = str(correlation_id)
                log_routing_decision(self._session, directive=directive, ledger=ledger, payload=payload)
                return ModelRouterResult(
                    decision="LOCAL",
                    primary_audit_code=br,
                    escalation_trigger_code=escalation_code,
                    blocked_external=True,
                    blocked_reason_code=br,
                    calibrated_confidence=ce.confidence,
                    local_adapter_raw_confidence=raw_conf,
                    signal_breakdown=ce.signals,
                    token_optimization=tok,
                    response_text=local_text,
                    local_model_profile_id=profile_id,
                    external_model_id=external_id,
                    optimized_prompt=optimized,
                )
        else:
            final_text = external_complete_stub(optimized_prompt=optimized, external_model_id=external_id)

        new_usage = add_external_usage_chars(directive.id, est_chars)

        tok = {
            **opt_meta,
            "external_path_taken": True,
            "optimized_prompt_chars": est_chars,
            "budget_usage_after": new_usage,
            "budget_limit": max_b,
        }
        if used_model_plane and correlation_id is not None:
            tok["model_plane_correlation_id"] = str(correlation_id)

        if (
            max_b > 0
            and new_usage >= self._settings.model_router_external_budget_warn_ratio * max_b
        ):
            log_budget_warning(
                self._session,
                directive=directive,
                ledger=ledger,
                payload={
                    "directive_id": str(directive.id),
                    "usage_chars": new_usage,
                    "budget_max_chars": max_b,
                    "warn_ratio": self._settings.model_router_external_budget_warn_ratio,
                },
            )

        primary = escalation_code or ""
        payload = self._payload_base(
            directive=directive,
            ledger=ledger,
            profile_id=profile_id,
            routing_outcome="EXTERNAL",
            escalation_code=escalation_code,
            blocked_external=False,
            blocked_code=None,
            primary=primary,
            calibrated=ce.confidence,
            raw_conf=raw_conf,
            signals=ce.signals,
            token_meta=tok,
            external_id=external_id,
        )
        if used_model_plane and correlation_id is not None:
            payload["model_plane_correlation_id"] = str(correlation_id)
        log_routing_decision(self._session, directive=directive, ledger=ledger, payload=payload)

        return ModelRouterResult(
            decision="EXTERNAL",
            primary_audit_code=primary,
            escalation_trigger_code=escalation_code,
            blocked_external=False,
            blocked_reason_code=None,
            calibrated_confidence=ce.confidence,
            local_adapter_raw_confidence=raw_conf,
            signal_breakdown=ce.signals,
            token_optimization=tok,
            response_text=final_text,
            local_model_profile_id=profile_id,
            external_model_id=external_id,
            optimized_prompt=optimized,
        )

    def _payload_base(
        self,
        *,
        directive: Directive,
        ledger: TaskLedger,
        profile_id: str,
        routing_outcome: str,
        escalation_code: str | None,
        blocked_external: bool,
        blocked_code: str | None,
        primary: str,
        calibrated: float,
        raw_conf: float,
        signals: dict[str, Any],
        token_meta: dict[str, Any],
        external_id: str | None,
    ) -> dict[str, Any]:
        return {
            "schema": "fix005_model_routing_v1",
            "routing_outcome": routing_outcome,
            "escalation_trigger_code": escalation_code,
            "blocked_external": blocked_external,
            "blocked_reason_code": blocked_code,
            "primary_audit_code": primary,
            "calibrated_confidence": calibrated,
            "local_adapter_raw_confidence": raw_conf,
            "signal_breakdown": signals,
            "token_optimization": token_meta,
            "task_id": str(ledger.id),
            "directive_id": str(directive.id),
            "local_model": profile_id,
            "external_model": external_id,
        }
