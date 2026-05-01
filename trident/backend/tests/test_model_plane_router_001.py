"""TRIDENT_IMPLEMENTATION_DIRECTIVE_MODEL_ROUTER_001 — model plane wiring (mocked httpx)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.config.settings import Settings
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.services.model_router import (
    AUDIT_SCHEMA,
    ModelPlaneReasonCode,
    ModelPlaneRequestType,
    ModelPlaneRouterService,
    ModelPlaneUnavailableError,
    ModelPlaneHttpRoute,
)


@pytest.fixture(autouse=True)
def _reset_plane_router():
    ModelPlaneRouterService.reset_for_tests()
    yield
    ModelPlaneRouterService.reset_for_tests()


@pytest.fixture
def mock_transport_factory():
    def _make(
        *,
        primary_tags: bool = False,
        secondary_tags: bool = False,
        ready_json: dict | None = None,
    ) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "ready.example" in url:
                return httpx.Response(200, json=ready_json or {"accept_inference": True})
            if "/api/tags" in url:
                if "plane-a.example" in url:
                    return _tags_ok() if primary_tags else httpx.Response(503)
                if "plane-b.example" in url:
                    return _tags_ok() if secondary_tags else httpx.Response(503)
            return httpx.Response(404)

        return httpx.MockTransport(handler)

    return _make


def _tags_ok():
    return httpx.Response(200, json={"models": []})


def test_select_primary_default(mock_transport_factory):
    cfg = Settings(
        model_router_base_url="http://plane-a.example:11434",
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
    )
    client = httpx.Client(transport=mock_transport_factory(primary_tags=True))
    svc = ModelPlaneRouterService.get_or_create(cfg, http_client=client)
    sel = svc.select_endpoint(ModelPlaneRequestType.CHAT)
    assert sel.plane == "primary"
    assert sel.reason_code == ModelPlaneReasonCode.PRIMARY_DEFAULT.value
    assert "plane-a.example" in sel.base_url


def test_secondary_skipped_without_prefer_secondary(mock_transport_factory):
    cfg = Settings(
        model_router_base_url="http://plane-a.example:11434",
        model_router_secondary_base_url="http://plane-b.example:11434",
        model_plane_secondary_enabled=True,
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
    )
    client = httpx.Client(transport=mock_transport_factory(primary_tags=True, secondary_tags=True))
    svc = ModelPlaneRouterService.get_or_create(cfg, http_client=client)
    sel = svc.select_endpoint(ModelPlaneRequestType.CHAT, prefer_secondary=False)
    assert sel.plane == "primary"


def test_secondary_selected_when_eligible_and_prefer(mock_transport_factory):
    cfg = Settings(
        model_router_base_url="http://plane-a.example:11434",
        model_router_secondary_base_url="http://plane-b.example:11434",
        model_plane_secondary_enabled=True,
        model_plane_secondary_ready_url="http://ready.example/ready",
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
    )
    client = httpx.Client(
        transport=mock_transport_factory(
            primary_tags=True,
            secondary_tags=True,
            ready_json={"accept_inference": True},
        )
    )
    svc = ModelPlaneRouterService.get_or_create(cfg, http_client=client)
    sel = svc.select_endpoint(ModelPlaneRequestType.EMBEDDING, prefer_secondary=True)
    assert sel.plane == "secondary"
    assert sel.reason_code == ModelPlaneReasonCode.SECONDARY_SELECTED.value


def test_secondary_blocked_when_ready_rejects(mock_transport_factory):
    cfg = Settings(
        model_router_base_url="http://plane-a.example:11434",
        model_router_secondary_base_url="http://plane-b.example:11434",
        model_plane_secondary_enabled=True,
        model_plane_secondary_ready_url="http://ready.example/ready",
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
    )
    client = httpx.Client(
        transport=mock_transport_factory(
            primary_tags=True,
            secondary_tags=True,
            ready_json={"accept_inference": False},
        )
    )
    svc = ModelPlaneRouterService.get_or_create(cfg, http_client=client)
    sel = svc.select_endpoint(ModelPlaneRequestType.CHAT, prefer_secondary=True)
    assert sel.plane == "primary"


def test_primary_unavailable_raises(mock_transport_factory):
    cfg = Settings(
        model_router_base_url="http://plane-a.example:11434",
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(503) if "/api/tags" in str(r.url) else httpx.Response(404))
    )
    svc = ModelPlaneRouterService.get_or_create(cfg, http_client=client)
    with pytest.raises(ModelPlaneUnavailableError) as ei:
        svc.select_endpoint(ModelPlaneRequestType.CHAT)
    assert ei.value.reason_code == ModelPlaneReasonCode.PRIMARY_UNAVAILABLE.value


def test_circuit_breaker_stops_probes(mock_transport_factory):
    cfg = Settings(
        model_router_base_url="http://plane-a.example:11434",
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
        model_plane_circuit_breaker_threshold=2,
        model_plane_circuit_breaker_ttl_sec=300.0,
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(503) if "/api/tags" in str(r.url) else httpx.Response(404))
    )
    svc = ModelPlaneRouterService.get_or_create(cfg, http_client=client)
    svc.probe_primary()
    svc.probe_primary()
    r3 = svc.probe_primary()
    assert not r3.ok
    assert r3.error == "circuit_open"


def test_audit_payload_model_plane_wiring(db_session, minimal_project_ids, mock_transport_factory):
    cfg = Settings(
        model_router_base_url="http://plane-a.example:11434",
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
    )
    client = httpx.Client(transport=mock_transport_factory(primary_tags=True))
    svc = ModelPlaneRouterService.get_or_create(cfg, http_client=client)
    svc.select_endpoint(
        ModelPlaneRequestType.CHAT,
        session=db_session,
        directive_id=None,
        project_id=minimal_project_ids["project_id"],
        workspace_id=minimal_project_ids["workspace_id"],
        correlation_id=str(uuid.uuid4()),
    )
    db_session.commit()
    row = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == AuditEventType.MODEL_ROUTING_DECISION.value)
        .order_by(AuditEvent.created_at.desc())
    )
    assert row is not None
    p = row.event_payload_json
    assert p["schema"] == AUDIT_SCHEMA
    assert p["plane"] == "primary"
    assert p["reason_code"] == ModelPlaneReasonCode.PRIMARY_DEFAULT.value
    assert p["request_type"] == "chat"
    assert "latency_ms_primary" in p


def test_call_model_posts_generate(mock_transport_factory):
    cfg = Settings(
        model_router_base_url="http://plane-a.example:11434",
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "/api/tags" in str(request.url):
            return _tags_ok()
        if request.method == "POST" and "/api/generate" in str(request.url):
            return httpx.Response(200, json={"done": True})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    svc = ModelPlaneRouterService.get_or_create(cfg, http_client=client)
    out = svc.call_model(ModelPlaneHttpRoute.GENERATE, {"model": "m", "prompt": "hi"})
    assert out == {"done": True}


def test_model_plane_status_endpoint(client):
    r = client.get("/api/v1/system/model-plane-status")
    assert r.status_code == 200
    data = r.json()
    assert "primary_healthy" in data
    assert "secondary_configured" in data
    assert "secondary_eligible" in data
    assert "last_selection_reason" in data
    assert "last_probe_at" in data
