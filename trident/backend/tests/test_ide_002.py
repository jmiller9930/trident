"""IDE_002 — tests for status + proof-summary endpoints and cadre registry."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.model_router.registry import (
    EXTERNAL_MODEL_ARCHITECT,
    EXTERNAL_MODEL_ENGINEER,
    LOCAL_PROFILE_ENGINEER,
    LOCAL_PROFILE_ARCHITECT,
    resolve_external_model_id,
    resolve_profile_id,
)
from app.models.enums import AgentRole
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.workflow.spine import run_spine_workflow


# ── helpers ────────────────────────────────────────────────────────────────────

def _create_and_run(db: Session, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="ide_002 status test",
        graph_id="ide002-v1",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db).create_directive_and_initialize(body)
    db.commit()
    run_spine_workflow(db, d.id, reviewer_rejections_remaining=0)
    db.commit()
    return d.id


# ── cadre registry ─────────────────────────────────────────────────────────────

def test_cadre_mode_engineer_local_profile():
    cfg = Settings(model_router_mode="CADRE_MODE")
    assert resolve_profile_id(agent_role=AgentRole.ENGINEER, settings=cfg) == LOCAL_PROFILE_ENGINEER


def test_cadre_mode_architect_local_profile():
    cfg = Settings(model_router_mode="CADRE_MODE")
    assert resolve_profile_id(agent_role=AgentRole.ARCHITECT, settings=cfg) == LOCAL_PROFILE_ARCHITECT


def test_single_mode_falls_back_to_shared_profile():
    cfg = Settings(model_router_mode="SINGLE_MODEL_MODE", model_router_shared_profile_id="my_shared")
    for role in (AgentRole.ENGINEER, AgentRole.ARCHITECT, AgentRole.REVIEWER):
        assert resolve_profile_id(agent_role=role, settings=cfg) == "my_shared"


def test_cadre_mode_external_engineer_is_sonnet():
    cfg = Settings(model_router_mode="CADRE_MODE")
    assert resolve_external_model_id(agent_role=AgentRole.ENGINEER, settings=cfg) == EXTERNAL_MODEL_ENGINEER


def test_cadre_mode_external_architect_is_opus():
    cfg = Settings(model_router_mode="CADRE_MODE")
    assert resolve_external_model_id(agent_role=AgentRole.ARCHITECT, settings=cfg) == EXTERNAL_MODEL_ARCHITECT


def test_single_mode_external_model_id_is_settings_default():
    cfg = Settings(model_router_mode="SINGLE_MODEL_MODE", model_router_external_stub_model_id="sonnet_46_external")
    assert resolve_external_model_id(agent_role=AgentRole.ENGINEER, settings=cfg) == "sonnet_46_external"


# ── /ide/status/{directive_id} ─────────────────────────────────────────────────

def test_ide_status_returns_expected_shape(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did = _create_and_run(db_session, minimal_project_ids)
    r = client.get(f"/api/v1/ide/status/{did}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["directive_status"] == "COMPLETE"
    assert data["ledger_state"] == "CLOSED"
    assert "title" in data
    assert "current_agent_role" in data
    assert "last_routing_decision" in data


def test_ide_status_404_for_unknown(client: TestClient) -> None:
    r = client.get(f"/api/v1/ide/status/{uuid.uuid4()}")
    assert r.status_code == 404


# ── /ide/proof-summary/{directive_id} ─────────────────────────────────────────

def test_ide_proof_summary_returns_expected_shape(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    did = _create_and_run(db_session, minimal_project_ids)
    r = client.get(f"/api/v1/ide/proof-summary/{did}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["directive_status"] == "COMPLETE"
    assert data["ledger_state"] == "CLOSED"
    assert isinstance(data["proof_count"], int)
    assert isinstance(data["last_mcp_events"], list)
    assert "last_routing_decision" in data
    assert "title" in data


def test_ide_proof_summary_no_raw_internal_keys(client: TestClient, db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    """Ensure no raw internal schema fields leak (no 'schema' or 'signal_breakdown' keys)."""
    did = _create_and_run(db_session, minimal_project_ids)
    r = client.get(f"/api/v1/ide/proof-summary/{did}")
    data = r.json()
    routing = data.get("last_routing_decision") or {}
    assert "schema" not in routing
    assert "signal_breakdown" not in routing
    assert "token_optimization" not in routing


def test_ide_proof_summary_404_for_unknown(client: TestClient) -> None:
    r = client.get(f"/api/v1/ide/proof-summary/{uuid.uuid4()}")
    assert r.status_code == 404


# ── model id in audit payload after escalation ────────────────────────────────

def test_external_model_label_in_routing_audit(db_session: Session, minimal_project_ids: dict[str, uuid.UUID]) -> None:
    from sqlalchemy import select
    from app.model_router.model_router_service import ModelRouterService
    from app.models.audit_event import AuditEvent
    from app.models.enums import AuditEventType

    body = CreateDirectiveRequest(
        workspace_id=minimal_project_ids["workspace_id"],
        project_id=minimal_project_ids["project_id"],
        title="LOWCONF cadre test",
        graph_id="ide002-cadre",
        created_by_user_id=minimal_project_ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()

    cfg = Settings(
        model_router_mode="CADRE_MODE",
        model_router_escalation_enabled=True,
        model_router_escalation_confidence_threshold=0.5,
    )
    svc = ModelRouterService(db_session, cfg)
    result = svc.route(
        directive=d,
        ledger=ledger,
        agent_role=AgentRole.ENGINEER,
        prompt=f"LOWCONF title={d.title}",
    )
    db_session.commit()

    assert result.decision == "EXTERNAL"
    assert result.external_model_id == EXTERNAL_MODEL_ENGINEER

    row = db_session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.directive_id == d.id,
            AuditEvent.event_type == AuditEventType.MODEL_ROUTING_DECISION.value,
        )
        .limit(1)
    ).first()
    assert row is not None
    payload = row.event_payload_json
    assert payload.get("external_model") == EXTERNAL_MODEL_ENGINEER
