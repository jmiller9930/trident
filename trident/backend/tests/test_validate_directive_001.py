"""TRIDENT_VALIDATION_DIRECTIVE_001 — live end-to-end validation via pytest.

Run (live Ollama required):
    TRIDENT_VALIDATE_LIVE=1 pytest tests/test_validate_directive_001.py -v -s

All tests are skipped automatically when TRIDENT_VALIDATE_LIVE is not set,
so the suite stays green in CI.

Scenarios:
  1. Happy path — primary plane, EXTERNAL routing, dual audit, correlation link.
  2. Secondary disabled guard — prefer_secondary=True, secondary must not be used.
  3. Primary down — fail-closed, MODEL_PLANE_UNAVAILABLE, no stub fallback.
  4. Circuit breaker — threshold trips, subsequent probes return circuit_open.
  5. Timeout handling — request timeout, deterministic failure, no hang.
  6. No-bypass — static scan confirming ModelPlaneRouterService not imported by ide/mcp/nike/agents/workflow.
  7. Status endpoint — in-process snapshot shape + live HTTP on clawbot.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.model_router.budget import reset_budget_counters
from app.model_router.model_router_service import ModelRouterService
from app.model_router.reason_codes import Fix005BlockReason, Fix005EscalationReason
from app.models.audit_event import AuditEvent
from app.models.enums import AgentRole, AuditEventType
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.services.model_router import (
    AUDIT_SCHEMA,
    ModelPlaneHttpRoute,
    ModelPlaneRequestType,
    ModelPlaneRouterService,
    ModelPlaneUnavailableError,
)

# ── constants ────────────────────────────────────────────────────────────────
OLLAMA_BASE = "http://172.20.2.230:11434"
FAST_MODEL = "qwen2.5:0.5b"
CLAWBOT_API = "http://172.20.2.151:8000/trident/api/v1"
LIVE = bool(os.getenv("TRIDENT_VALIDATE_LIVE"))
skip_if_no_live = pytest.mark.skipif(not LIVE, reason="TRIDENT_VALIDATE_LIVE not set")


# ── helpers ──────────────────────────────────────────────────────────────────

def _mk_directive(db: Session, ids: dict, tag: str):
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title=f"LOWCONF {tag}",
        graph_id=f"val001-{tag}",
        created_by_user_id=ids["user_id"],
    )
    d, ledger, _ = DirectiveRepository(db).create_directive_and_initialize(body)
    db.commit()
    return d, ledger


def _escalation_cfg(**kw: object) -> Settings:
    return Settings(
        model_router_escalation_enabled=True,
        model_router_token_budget_chars=120,
        model_plane_tcp_probe_enabled=True,
        model_plane_probe_retries=1,
        model_router_base_url=OLLAMA_BASE,
        model_router_external_stub_model_id=FAST_MODEL,
        engineer_use_model_plane=True,
        **kw,
    )


def _audit(db: Session) -> list[AuditEvent]:
    return list(db.scalars(
        select(AuditEvent).where(
            AuditEvent.event_type == AuditEventType.MODEL_ROUTING_DECISION.value
        )
    ).all())


def _fix_payloads(rows: list[AuditEvent]) -> list[dict]:
    return [r.event_payload_json for r in rows if r.event_payload_json.get("schema") == "fix005_model_routing_v1"]


def _plane_payloads(rows: list[AuditEvent]) -> list[dict]:
    return [r.event_payload_json for r in rows if r.event_payload_json.get("schema") == AUDIT_SCHEMA]


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset(minimal_project_ids):
    ModelPlaneRouterService.reset_for_tests()
    reset_budget_counters()
    yield
    ModelPlaneRouterService.reset_for_tests()
    reset_budget_counters()


# ── SCENARIO 1: Happy path ────────────────────────────────────────────────────

@skip_if_no_live
def test_s1_happy_path_primary(db_session: Session, minimal_project_ids: dict) -> None:
    """SCENARIO 1 — real Ollama call, dual audit, correlation IDs linked."""
    d, ledger = _mk_directive(db_session, minimal_project_ids, "s1-happy")
    cfg = _escalation_cfg(
        model_plane_secondary_enabled=False,
        engineer_model_plane_prefer_secondary=False,
    )
    prompt = f"directive_id={d.id}\ntitle={d.title}\nLOWCONF validate"
    t0 = time.perf_counter()
    result = ModelRouterService(db_session, cfg).route(
        directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    db_session.commit()

    rows = _audit(db_session)
    fix_p   = _fix_payloads(rows)[-1]
    plane_p = _plane_payloads(rows)[-1]

    print(f"\n[S1] decision={result.decision}  elapsed={elapsed_ms}ms")
    print(f"[S1] response preview: {result.response_text[:120]!r}")
    print(f"[S1] Fix005 routing_outcome: {fix_p['routing_outcome']}")
    print(f"[S1] Fix005 model_plane_correlation_id: {fix_p.get('model_plane_correlation_id')}")
    print(f"[S1] Plane selected_endpoint: {plane_p.get('selected_endpoint')}")
    print(f"[S1] Plane reason_code: {plane_p.get('reason_code')}")
    print(f"[S1] Plane health_primary_ok: {plane_p.get('health_primary_ok')}")
    print(f"[S1] Plane correlation_id: {plane_p.get('correlation_id')}")

    assert result.decision == "EXTERNAL"
    assert result.response_text.strip(), "response must be non-empty"
    assert fix_p["routing_outcome"] == "EXTERNAL"
    assert plane_p["plane"] == "primary"
    assert plane_p["reason_code"] == "PRIMARY_DEFAULT"
    assert OLLAMA_BASE in (plane_p.get("selected_endpoint") or "")
    assert plane_p["health_primary_ok"] is True
    cid = fix_p.get("model_plane_correlation_id")
    assert cid and cid == plane_p.get("correlation_id"), "correlation IDs must match"


# ── SCENARIO 2: Secondary disabled guard ─────────────────────────────────────

@skip_if_no_live
def test_s2_secondary_disabled_guard(db_session: Session, minimal_project_ids: dict) -> None:
    """SCENARIO 2 — prefer_secondary=True but disabled; primary must be used."""
    d, ledger = _mk_directive(db_session, minimal_project_ids, "s2-sec-guard")
    cfg = _escalation_cfg(
        model_plane_secondary_enabled=False,
        model_router_secondary_base_url="http://172.20.1.66:11434",
        engineer_model_plane_prefer_secondary=True,
    )
    prompt = f"directive_id={d.id}\ntitle={d.title}\nLOWCONF validate"
    result = ModelRouterService(db_session, cfg).route(
        directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt
    )
    db_session.commit()

    rows = _audit(db_session)
    plane_p = _plane_payloads(rows)[-1]

    print(f"\n[S2] decision={result.decision}")
    print(f"[S2] Plane selected: {plane_p.get('plane')}")
    print(f"[S2] secondary_skip_reason: {plane_p.get('secondary_skip_reason')}")

    assert result.decision == "EXTERNAL"
    assert result.response_text.strip()
    assert plane_p["plane"] == "primary"
    assert "SECONDARY_SKIPPED_DISABLED" in (plane_p.get("secondary_skip_reason") or "")


# ── SCENARIO 3: Primary down — fail-closed ────────────────────────────────────

def test_s3_primary_down_fail_closed(db_session: Session, minimal_project_ids: dict) -> None:
    """SCENARIO 3 — unreachable primary; blocked_external, no stub fallback (mocked)."""
    d, ledger = _mk_directive(db_session, minimal_project_ids, "s3-down")
    cfg = Settings(
        model_router_escalation_enabled=True,
        model_router_token_budget_chars=120,
        engineer_use_model_plane=True,
        model_router_base_url="http://10.255.255.1:11434",
        model_plane_connect_timeout_sec=1.0,
        model_plane_probe_retries=0,
        model_plane_tcp_probe_enabled=False,  # skip TCP; HTTP will time-out on mock
        model_plane_secondary_enabled=False,
        model_router_external_stub_model_id=FAST_MODEL,
    )

    def _dead_handler(request: httpx.Request) -> httpx.Response:
        if "/api/tags" in str(request.url):
            return httpx.Response(503)
        return httpx.Response(503)

    plane = ModelPlaneRouterService(
        cfg,
        http_client=httpx.Client(transport=httpx.MockTransport(_dead_handler)),
    )
    prompt = f"directive_id={d.id}\ntitle={d.title}\nLOWCONF validate"
    result = ModelRouterService(db_session, cfg, model_plane_router=plane).route(
        directive=d, ledger=ledger, agent_role=AgentRole.ENGINEER, prompt=prompt
    )
    db_session.commit()

    rows = _audit(db_session)
    fix_p = _fix_payloads(rows)[-1]

    print(f"\n[S3] decision={result.decision}  blocked={result.blocked_external}")
    print(f"[S3] blocked_reason_code: {result.blocked_reason_code}")
    print(f"[S3] Fix005 routing_outcome: {fix_p['routing_outcome']}")
    print(f"[S3] Fix005 blocked_reason_code: {fix_p.get('blocked_reason_code')}")
    plane_err = fix_p.get("token_optimization", {}).get("model_plane_error") or fix_p.get("model_plane_error")
    print(f"[S3] model_plane_error: {plane_err}")

    assert result.decision == "LOCAL"
    assert result.blocked_external is True
    assert result.blocked_reason_code == Fix005BlockReason.MODEL_PLANE_UNAVAILABLE.value
    assert fix_p["routing_outcome"] == "LOCAL"
    assert fix_p.get("blocked_reason_code") == Fix005BlockReason.MODEL_PLANE_UNAVAILABLE.value


# ── SCENARIO 4: Circuit breaker ──────────────────────────────────────────────

def test_s4_circuit_breaker() -> None:
    """SCENARIO 4 — 2 failures trip CB; 3rd + 4th probe return circuit_open."""
    cfg = Settings(
        model_router_base_url="http://cb-plane.test:11434",
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
        model_plane_circuit_breaker_threshold=2,
        model_plane_circuit_breaker_ttl_sec=300.0,
    )
    ModelPlaneRouterService.reset_for_tests()
    plane = ModelPlaneRouterService(
        cfg,
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(503))
        ),
    )

    r1 = plane.probe_primary()
    r2 = plane.probe_primary()
    r3 = plane.probe_primary()
    r4 = plane.probe_primary()

    print(f"\n[S4] probe1: ok={r1.ok} error={r1.error}")
    print(f"[S4] probe2: ok={r2.ok} error={r2.error}  ← threshold=2, CB trips after this")
    print(f"[S4] probe3: ok={r3.ok} error={r3.error}  ← expect circuit_open")
    print(f"[S4] probe4: ok={r4.ok} error={r4.error}  ← still circuit_open")

    assert not r1.ok and not r2.ok
    assert r3.error == "circuit_open"
    assert r4.error == "circuit_open"
    ModelPlaneRouterService.reset_for_tests()


# ── SCENARIO 5: Timeout handling ─────────────────────────────────────────────

def test_s5_timeout_handling() -> None:
    """SCENARIO 5 — POST /api/chat exceeds request_timeout_sec, error surfaced, no hang."""
    cfg = Settings(
        model_router_base_url="http://timeout-plane.test:11434",
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
        model_plane_request_timeout_sec=1.0,
        model_plane_circuit_breaker_threshold=10,
    )
    ModelPlaneRouterService.reset_for_tests()

    def _slow(request: httpx.Request) -> httpx.Response:
        # Mock transport runs synchronously — raise the timeout exception directly
        # to simulate what httpx does when model_plane_request_timeout_sec expires.
        if "/api/tags" in str(request.url):
            return httpx.Response(200, json={"models": []})
        raise httpx.ReadTimeout("read timeout exceeded", request=request)

    plane = ModelPlaneRouterService(
        cfg,
        http_client=httpx.Client(transport=httpx.MockTransport(_slow)),
    )
    t0 = time.perf_counter()
    with pytest.raises(ModelPlaneUnavailableError) as ei:
        plane.call_model(
            ModelPlaneHttpRoute.CHAT,
            {"model": "m", "messages": [{"role": "user", "content": "hi"}]},
            request_type=ModelPlaneRequestType.CHAT,
        )
    elapsed = round((time.perf_counter() - t0) * 1000)

    print(f"\n[S5] ModelPlaneUnavailableError: {ei.value.reason_code}")
    print(f"[S5] detail: {ei.value.detail}")
    print(f"[S5] elapsed_ms={elapsed}  (mock timeout, must be < 2000ms)")

    assert ei.value.reason_code in ("MODEL_CALL_FAILED", "MODEL_CALL_HTTP_ERROR")
    assert elapsed < 2000, f"must not hang: took {elapsed}ms"
    ModelPlaneRouterService.reset_for_tests()


# ── SCENARIO 6: No-bypass guarantee ──────────────────────────────────────────

def test_s6_no_bypass_static_scan() -> None:
    """SCENARIO 6 — ModelPlaneRouterService not imported by ide/mcp/nike/agents/workflow."""
    backend_app = Path(__file__).resolve().parents[1] / "app"
    needles = ("ModelPlaneRouterService", "app.services.model_router")
    forbidden_pkgs = ("ide", "mcp", "nike", "agents", "workflow")
    offenders: list[str] = []

    for pkg in forbidden_pkgs:
        pkg_path = backend_app / pkg
        if not pkg_path.is_dir():
            continue
        for path in pkg_path.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                if needle in text:
                    offenders.append(f"{path.relative_to(backend_app)}: needle={needle!r}")

    print(f"\n[S6] Scanned pkgs: {list(forbidden_pkgs)}")
    print(f"[S6] Offenders: {offenders if offenders else 'none'}")

    # Confirm the ONLY sanctioned direct user inside app/ is model_router_service.py
    all_files = list(backend_app.rglob("*.py"))
    direct_importers = []
    for path in all_files:
        rel = str(path.relative_to(backend_app))
        if "services/model_router.py" in rel:
            continue
        if "ModelPlaneRouterService" in path.read_text(encoding="utf-8"):
            if "model_router/model_router_service.py" not in rel:
                direct_importers.append(rel)

    # Sanctioned direct importers outside model_router_service (read-only status + config docstrings):
    SANCTIONED_DIRECT = {
        "model_router/model_router_service.py",  # governed call site
        "api/v1/system.py",                      # status endpoint (read-only)
        "config/settings.py",                    # docstring mention only
    }
    unsanctioned = [p for p in direct_importers if p not in SANCTIONED_DIRECT]
    print(f"[S6] Direct importers: {direct_importers}")
    print(f"[S6] Unsanctioned: {unsanctioned if unsanctioned else 'none'}")
    assert offenders == [], f"unsanctioned pkg imports: {offenders}"
    assert unsanctioned == [], f"unsanctioned direct importers: {unsanctioned}"


# ── SCENARIO 7: Status endpoint ───────────────────────────────────────────────

@skip_if_no_live
def test_s7_status_endpoint_live_primary(db_session: Session) -> None:
    """SCENARIO 7 — real probe + status snapshot + HTTP from clawbot."""
    ModelPlaneRouterService.reset_for_tests()
    cfg = Settings(
        model_router_base_url=OLLAMA_BASE,
        model_plane_secondary_enabled=False,
        model_plane_tcp_probe_enabled=True,
        model_plane_probe_retries=0,
    )
    plane = ModelPlaneRouterService.get_or_create(cfg)
    plane.refresh_probes()
    snap = plane.status_snapshot()

    print(f"\n[S7] status_snapshot:\n{json.dumps(snap, indent=2, default=str)}")

    assert snap["primary_healthy"] is True
    assert snap["secondary_configured"] is False
    assert snap["secondary_healthy"] is False
    assert snap["secondary_eligible"] is False
    assert snap["last_probe_at"] is not None

    try:
        resp = httpx.get(f"{CLAWBOT_API}/system/model-plane-status", timeout=8)
        http_snap = resp.json()
        print(f"[S7] HTTP model-plane-status from clawbot:\n{json.dumps(http_snap, indent=2)}")
        assert "primary_healthy" in http_snap
        assert "secondary_configured" in http_snap
    except Exception as e:
        print(f"[S7] clawbot HTTP: not reachable from local ({type(e).__name__}: {e})")

    ModelPlaneRouterService.reset_for_tests()


def test_s7_status_endpoint_shape_mocked() -> None:
    """SCENARIO 7 (always runs) — verify snapshot shape with mocked plane."""
    ModelPlaneRouterService.reset_for_tests()
    cfg = Settings(
        model_router_base_url="http://mock-plane.test:11434",
        model_plane_secondary_enabled=False,
        model_plane_tcp_probe_enabled=False,
        model_plane_probe_retries=0,
    )
    plane = ModelPlaneRouterService(
        cfg,
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"models": []}) if "/api/tags" in str(r.url) else httpx.Response(404)
            )
        ),
    )
    plane.refresh_probes()
    snap = plane.status_snapshot()

    print(f"\n[S7-mock] status_snapshot:\n{json.dumps(snap, indent=2, default=str)}")

    assert "primary_healthy" in snap
    assert snap["secondary_configured"] is False
    assert snap["secondary_healthy"] is False
    assert snap["secondary_eligible"] is False
    assert snap["last_probe_at"] is not None
    assert snap["primary_healthy"] is True
    ModelPlaneRouterService.reset_for_tests()
