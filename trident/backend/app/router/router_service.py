"""Subsystem router orchestration — no execution side effects (100G)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.router.router_classifier import RouterRoute, classify_intent, next_action_hint
from app.router.router_logger import RouterAuditLogger
from app.router.router_validator import resolve_router_context
from app.schemas.router import RouterRouteRequest, RouterRouteResponse


class RouterService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._log = RouterAuditLogger(session)

    def decide(self, body: RouterRouteRequest) -> RouterRouteResponse:
        directive, _ledger, role_val = resolve_router_context(
            self._session,
            directive_id=body.directive_id,
            task_id=body.task_id,
            agent_role=body.agent_role,
            intent=body.intent,
        )

        route, rationale = classify_intent(body.intent)
        payload_keys = sorted(body.payload.keys()) if body.payload else []

        if route is None:
            resp = RouterRouteResponse(
                route=None,
                reason=rationale,
                next_action="",
                validated=False,
            )
            self._log.decision_made(
                directive,
                task_id=body.task_id,
                agent_role=role_val,
                intent_preview=body.intent,
                payload_keys=payload_keys,
                decision_payload={
                    "validated": False,
                    "route": None,
                    "reason_code": rationale,
                },
            )
            return resp

        hint = next_action_hint(route)
        resp = RouterRouteResponse(
            route=route.value,
            reason=rationale,
            next_action=hint,
            validated=True,
        )
        self._log.decision_made(
            directive,
            task_id=body.task_id,
            agent_role=role_val,
            intent_preview=body.intent,
            payload_keys=payload_keys,
            decision_payload={
                "validated": True,
                "route": route.value,
                "reason_code": rationale,
                "next_action": hint,
            },
        )
        return resp
