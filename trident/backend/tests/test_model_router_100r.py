"""100R / FIX 005 — model router (backend-only; LangGraph hook)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import Settings
from app.db.session import get_db
from app.main import build_app
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType, AgentRole
from app.model_router.budget import reset_budget_counters
from app.model_router.health import model_router_health_snapshot, trigger_benchmark_audit
from app.model_router.model_router_service import ModelRouterService
from app.model_router.reason_codes import Fix005BlockReason, Fix005EscalationReason, Fix005LocalOutcome
from app.model_router.registry import resolve_profile_id
from app.model_router.token_optimizer import optimize_prompt_for_external
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest


@pytest.fixture(autouse=True)
def _reset_model_router_budget_counters() -> None:
    reset_budget_counters()
    yield
    reset_budget_counters()


def test_token_optimizer_trims() -> None:
    long_p = "x" * 9000
    out, meta = optimize_prompt_for_external(long_p, max_chars=100)
    assert meta["trimmed"] is True
    assert meta["original_chars"] == 9000
    assert len(out) <= 200
    assert "truncated" in out


def test_resolve_profile_single_vs_cadre() -> None:
    single = Settings(model_router_mode="SINGLE_MODEL_MODE", model_router_shared_profile_id="shared_x")
    assert resolve_profile_id(agent_role=AgentRole.ENGINEER, settings=single) == "shared_x"
    cadre = Settings(model_router_mode="CADRE_MODE", model_router_shared_profile_id="fallback_shared")
    from app.model_router.registry import LOCAL_PROFILE_ENGINEER
    assert resolve_profile_id(agent_role=AgentRole.ENGINEER, settings=cadre) == LOCAL_PROFILE_ENGINEER


def test_model_router_service_local_only_default(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="normal title HIGHCONF path",
        graph_id="mr-v1",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = Settings(model_router_escalation_enabled=False)
    svc = ModelRouterService(db_session, cfg)
    r = svc.route(
        directive=d,
        ledger=ledger,
        agent_role=AgentRole.ENGINEER,
        prompt="noop prompt",
    )
    assert r.decision == "LOCAL"
    assert r.primary_audit_code == Fix005LocalOutcome.LOCAL_COMPLETED.value
    assert r.escalation_trigger_code is None


def test_model_router_escalates_with_explicit_reason(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="LOWCONF trigger",
        graph_id="mr-v2",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = Settings(model_router_escalation_enabled=True, model_router_token_budget_chars=120)
    prompt = f"directive_id={d.id}\ntitle={d.title}\n"
    svc = ModelRouterService(db_session, cfg)
    r = svc.route(directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt)
    assert r.decision == "EXTERNAL"
    assert r.escalation_trigger_code == Fix005EscalationReason.LOW_CONFIDENCE.value
    assert r.primary_audit_code == Fix005EscalationReason.LOW_CONFIDENCE.value
    assert r.external_model_id == cfg.model_router_external_stub_model_id
    assert r.signal_breakdown.get("final_calibrated_confidence") is not None
    assert r.token_optimization.get("trimmed") is False or r.token_optimization.get("trimmed") is True


def test_external_disabled_blocks_lowconf_with_audit_codes(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="LOWCONF blocked",
        graph_id="mr-b1",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = Settings(model_router_escalation_enabled=False)
    prompt = f"title={d.title}\nLOWCONF\n"
    r = ModelRouterService(db_session, cfg).route(
        directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt
    )
    assert r.decision == "LOCAL"
    assert r.blocked_external is True
    assert r.blocked_reason_code == Fix005BlockReason.EXTERNAL_ESCALATION_DISABLED.value
    assert r.escalation_trigger_code == Fix005EscalationReason.LOW_CONFIDENCE.value


def test_budget_blocks_external_path(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="LOWCONF budget",
        graph_id="mr-b2",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = Settings(
        model_router_escalation_enabled=True,
        model_router_external_budget_max_chars=900,
        model_router_token_budget_chars=4096,
    )
    prompt = f"directive_id={d.id}\ntitle={d.title}\nLOWCONF\n" + ("y" * 400)
    svc = ModelRouterService(db_session, cfg)
    r1 = svc.route(directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt)
    assert r1.decision == "EXTERNAL"
    r2 = svc.route(directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt)
    assert r2.decision == "LOCAL"
    assert r2.blocked_reason_code == Fix005BlockReason.BUDGET_EXCEEDED.value


def test_budget_warning_audit_when_usage_crosses_ratio(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="LOWCONF warn",
        graph_id="mr-b3",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = Settings(
        model_router_escalation_enabled=True,
        model_router_external_budget_max_chars=400,
        model_router_external_budget_warn_ratio=0.8,
        model_router_token_budget_chars=4096,
    )
    prompt = f"title={d.title}\nLOWCONF\n" + ("z" * 300)
    before = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.event_type == AuditEventType.MODEL_ROUTING_BUDGET_WARNING.value
        )
    )
    ModelRouterService(db_session, cfg).route(directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt)
    db_session.commit()
    after = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.event_type == AuditEventType.MODEL_ROUTING_BUDGET_WARNING.value
        )
    )
    assert int(after or 0) >= int(before or 0) + 1


def test_system_model_router_status_endpoint(client: TestClient) -> None:
    r = client.get("/api/v1/system/model-router-status")
    assert r.status_code == 200
    data = r.json()
    assert "health" in data and "external_usage_chars_by_directive" in data
    assert data["health"]["mode"] == "SINGLE_MODEL_MODE"


def test_spine_engineer_emits_routing_audit(client: TestClient, db_session: Session, minimal_project_ids: dict) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="routing audit spine",
        graph_id="mr-v3",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    before = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.MODEL_ROUTING_DECISION.value)
    )
    lr = client.post(
        "/api/v1/auth/login",
        json={"email": minimal_project_ids["email"], "password": minimal_project_ids["password"]},
    )
    assert lr.status_code == 200, lr.text
    h = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
    r = client.post(
        f"/api/v1/directives/{d.id}/workflow/run?reviewer_rejections_remaining=0",
        headers=h,
    )
    assert r.status_code == 200, r.text
    after = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.MODEL_ROUTING_DECISION.value)
    )
    assert int(after or 0) >= int(before or 0) + 1


def test_health_snapshot_and_benchmark_hook(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="bench",
        graph_id="mr-v4",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    cfg = Settings()
    snap = model_router_health_snapshot(settings=cfg)
    assert snap["mode"] == "SINGLE_MODEL_MODE"
    assert "external_budget_max_chars" in snap
    trigger_benchmark_audit(db_session, directive=d, ledger=ledger, settings=cfg)
    db_session.commit()
    n = db_session.scalar(
        select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == AuditEventType.MODEL_ROUTER_BENCHMARK.value)
    )
    assert int(n or 0) >= 1


def test_run_spine_threads_app_settings_for_escalation(sqlite_engine, minimal_project_ids: dict) -> None:
    """Escalation path via Settings(model_router_escalation_enabled=True) + LOWCONF in composed prompt."""
    import app.models  # noqa: F401

    SessionLocal = sessionmaker(bind=sqlite_engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app = build_app(
        Settings(
            base_path="",
            lock_heartbeat_miss_sec=0,
            model_router_escalation_enabled=True,
            model_router_escalation_confidence_threshold=0.5,
            model_router_token_budget_chars=256,
        )
    )
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        db = SessionLocal()
        try:
            body = CreateDirectiveRequest(
                workspace_id=minimal_project_ids["workspace_id"],
                project_id=minimal_project_ids["project_id"],
                title="LOWCONF escalation integration",
                graph_id="mr-v5",
                created_by_user_id=minimal_project_ids["user_id"],
            )
            d, _, _ = DirectiveRepository(db).create_directive_and_initialize(body)
            db.commit()
            rid = d.id
        finally:
            db.close()

        lr = client.post(
            "/api/v1/auth/login",
            json={"email": minimal_project_ids["email"], "password": minimal_project_ids["password"]},
        )
        assert lr.status_code == 200, lr.text
        h = {"Authorization": f"Bearer {lr.json()['tokens']['access_token']}"}
        r = client.post(
            f"/api/v1/directives/{rid}/workflow/run?reviewer_rejections_remaining=0",
            headers=h,
        )
        assert r.status_code == 200, r.text

    db2 = SessionLocal()
    try:
        rows = list(
            db2.scalars(
                select(AuditEvent).where(
                    AuditEvent.directive_id == rid,
                    AuditEvent.event_type == AuditEventType.MODEL_ROUTING_DECISION.value,
                )
            ).all()
        )
        assert rows
        payloads = [x.event_payload_json for x in rows]
        assert any(p.get("routing_outcome") == "EXTERNAL" for p in payloads)
        assert any(p.get("escalation_trigger_code") == Fix005EscalationReason.LOW_CONFIDENCE.value for p in payloads)
        assert all(p.get("schema") == "fix005_model_routing_v1" for p in payloads)
    finally:
        db2.close()

    app.dependency_overrides.clear()


def test_audit_payload_has_signal_breakdown(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="audit signals",
        graph_id="mr-a1",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    ModelRouterService(db_session, Settings()).route(
        directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt="plain prompt"
    )
    db_session.commit()
    row = db_session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.directive_id == d.id,
            AuditEvent.event_type == AuditEventType.MODEL_ROUTING_DECISION.value,
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(1)
    ).first()
    assert row is not None
    js = row.event_payload_json
    assert js.get("signal_breakdown")
    assert js.get("calibrated_confidence") is not None
