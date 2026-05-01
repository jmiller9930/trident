"""MODEL_ROUTER_002 — Fix005 EXTERNAL branch wires ModelPlaneRouterService (governed path only)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
from sqlalchemy import select

from app.config.settings import Settings
from app.models.audit_event import AuditEvent
from app.models.enums import AgentRole, AuditEventType
from app.model_router.model_adapters.external_adapter import external_complete_stub
from app.model_router.model_router_service import ModelRouterService
from app.model_router.reason_codes import Fix005BlockReason, Fix005EscalationReason
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.services.model_router import (
    AUDIT_SCHEMA,
    ModelPlaneRouterService,
    ModelPlaneUnavailableError,
)


@pytest.fixture(autouse=True)
def _reset_plane_router_singleton():
    ModelPlaneRouterService.reset_for_tests()
    yield
    ModelPlaneRouterService.reset_for_tests()


def _external_escalation_settings(**kw: object) -> Settings:
    return Settings(
        model_router_escalation_enabled=True,
        model_router_token_budget_chars=120,
        **kw,
    )


def _mk_plane_http_client(model_name: str, reply: str) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        u = str(request.url)
        if "/api/tags" in u:
            return httpx.Response(200, json={"models": [{"name": model_name}]})
        if request.method == "POST" and "/api/chat" in u:
            return httpx.Response(200, json={"message": {"role": "assistant", "content": reply}})
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_external_uses_stub_when_engineer_plane_disabled(db_session, minimal_project_ids: dict) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="LOWCONF trigger",
        graph_id="mr002-a",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = _external_escalation_settings(engineer_use_model_plane=False)
    prompt = f"directive_id={d.id}\ntitle={d.title}\n"
    r = ModelRouterService(db_session, cfg).route(
        directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt
    )
    assert r.decision == "EXTERNAL"
    stub = external_complete_stub(
        optimized_prompt=r.optimized_prompt or "",
        external_model_id=cfg.model_router_external_stub_model_id,
    )
    assert r.response_text == stub


def test_external_uses_model_plane_when_enabled(db_session, minimal_project_ids: dict) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="LOWCONF trigger",
        graph_id="mr002-b",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = _external_escalation_settings(
        engineer_use_model_plane=True,
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
        model_router_base_url="http://ollama-plane.test:11434",
    )
    prompt = f"directive_id={d.id}\ntitle={d.title}\n"
    plane = ModelPlaneRouterService(
        cfg,
        http_client=_mk_plane_http_client(cfg.model_router_external_stub_model_id, "FROM_OLLAMA_CHAT"),
    )
    r = ModelRouterService(db_session, cfg, model_plane_router=plane).route(
        directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt
    )
    assert r.decision == "EXTERNAL"
    assert r.response_text == "FROM_OLLAMA_CHAT"
    assert r.token_optimization.get("model_plane_correlation_id")

    rows = list(
        db_session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == AuditEventType.MODEL_ROUTING_DECISION.value)
        ).all()
    )
    schemas = [x.event_payload_json.get("schema") for x in rows]
    assert "fix005_model_routing_v1" in schemas
    assert AUDIT_SCHEMA in schemas
    fix_rows = [x for x in rows if x.event_payload_json.get("schema") == "fix005_model_routing_v1"]
    plane_rows = [x for x in rows if x.event_payload_json.get("schema") == AUDIT_SCHEMA]
    assert fix_rows and plane_rows
    cid_fix = fix_rows[-1].event_payload_json.get("model_plane_correlation_id")
    cid_plane = plane_rows[-1].event_payload_json.get("correlation_id")
    assert cid_fix == cid_plane


def test_model_plane_failure_fail_closed_no_stub_fallback(db_session, minimal_project_ids: dict) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="LOWCONF trigger",
        graph_id="mr002-c",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = _external_escalation_settings(engineer_use_model_plane=True)
    boom = MagicMock()
    boom.call_model.side_effect = ModelPlaneUnavailableError(
        reason_code="PRIMARY_UNAVAILABLE",
        message="down",
        detail={},
    )

    prompt = f"directive_id={d.id}\ntitle={d.title}\n"
    r = ModelRouterService(db_session, cfg, model_plane_router=boom).route(  # type: ignore[arg-type]
        directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt
    )
    assert r.decision == "LOCAL"
    assert r.blocked_external is True
    assert r.primary_audit_code == Fix005BlockReason.MODEL_PLANE_UNAVAILABLE.value
    assert r.escalation_trigger_code == Fix005EscalationReason.LOW_CONFIDENCE.value


def test_local_path_unchanged_when_no_escalation(db_session, minimal_project_ids: dict) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="normal title HIGHCONF path",
        graph_id="mr002-d",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = Settings(
        engineer_use_model_plane=True,
        model_router_escalation_enabled=True,
    )
    r = ModelRouterService(db_session, cfg).route(
        directive=d,
        ledger=ledger,
        agent_role=AgentRole.ENGINEER,
        prompt="noop prompt",
    )
    assert r.decision == "LOCAL"
    assert r.blocked_external is False


def test_no_model_plane_router_import_in_ide_mcp_nike_packages() -> None:
    backend_app = Path(__file__).resolve().parents[1] / "app"
    needles = ("ModelPlaneRouterService", "app.services.model_router")
    offenders: list[str] = []
    for pkg in ("ide", "mcp", "nike"):
        pkg_path = backend_app / pkg
        if not pkg_path.is_dir():
            continue
        for path in pkg_path.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if any(n in text for n in needles):
                offenders.append(str(path.relative_to(backend_app)))
    assert offenders == [], f"unsanctioned model-plane imports: {offenders}"
