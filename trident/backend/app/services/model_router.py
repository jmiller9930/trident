"""Control-plane → model-plane routing (MODEL_PLANE_WIRING / TRIDENT_IMPLEMENTATION_DIRECTIVE_MODEL_ROUTER_001).

Not to be confused with ``app.model_router.ModelRouterService`` (Fix005 confidence/escalation).
"""

from __future__ import annotations

import json
import random
import socket
import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.enums import AuditActorType, AuditEventType
from app.repositories.audit_repository import AuditRepository

AUDIT_SCHEMA = "model_plane_wiring_v1"


class ModelPlaneRequestType(StrEnum):
    CHAT = "chat"
    EMBEDDING = "embedding"


class ModelPlaneHttpRoute(StrEnum):
    GENERATE = "generate"
    CHAT = "chat"
    EMBEDDINGS = "embeddings"


_ROUTE_PATHS: dict[str, str] = {
    ModelPlaneHttpRoute.GENERATE.value: "/api/generate",
    ModelPlaneHttpRoute.CHAT.value: "/api/chat",
    ModelPlaneHttpRoute.EMBEDDINGS.value: "/api/embeddings",
}


class ModelPlaneReasonCode(StrEnum):
    PRIMARY_DEFAULT = "PRIMARY_DEFAULT"
    PRIMARY_UNAVAILABLE = "PRIMARY_UNAVAILABLE"
    PRIMARY_CIRCUIT_OPEN = "PRIMARY_CIRCUIT_OPEN"
    SECONDARY_SELECTED = "SECONDARY_SELECTED"
    SECONDARY_SKIPPED_DISABLED = "SECONDARY_SKIPPED_DISABLED"
    SECONDARY_SKIPPED_NOT_CONFIGURED = "SECONDARY_SKIPPED_NOT_CONFIGURED"
    SECONDARY_SKIPPED_UNHEALTHY = "SECONDARY_SKIPPED_UNHEALTHY"
    SECONDARY_SKIPPED_READY_REJECTED = "SECONDARY_SKIPPED_READY_REJECTED"
    SECONDARY_SKIPPED_CIRCUIT_OPEN = "SECONDARY_SKIPPED_CIRCUIT_OPEN"


@dataclass
class ProbeResult:
    ok: bool
    latency_ms: float | None = None
    retry_count: int = 0
    error: str | None = None


@dataclass
class SelectedEndpoint:
    base_url: str
    plane: str  # primary | secondary
    reason_code: str


@dataclass
class _CircuitBreaker:
    failures: int = 0
    opened_until_monotonic: float | None = None

    def is_open(self, now: float) -> bool:
        if self.opened_until_monotonic is None:
            return False
        if now < self.opened_until_monotonic:
            return True
        self.opened_until_monotonic = None
        self.failures = 0
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_until_monotonic = None

    def record_failure(self, *, threshold: int, ttl_sec: float, now: float) -> None:
        self.failures += 1
        if self.failures >= threshold:
            self.opened_until_monotonic = now + ttl_sec


def _normalize_base(url: str) -> str:
    s = (url or "").strip().rstrip("/")
    return s


def _parse_host_port(base_url: str) -> tuple[str, int]:
    p = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = p.hostname or "127.0.0.1"
    port = p.port or (443 if p.scheme == "https" else 80)
    return host, port


def _backoff_sleep(attempt: int) -> None:
    base = 0.25 * (2**attempt)
    jitter = random.uniform(0.05, 0.15)
    time.sleep(base + jitter)


class ModelPlaneUnavailableError(Exception):
    """Fail-closed when primary model plane cannot be used."""

    def __init__(self, *, reason_code: str, message: str, detail: dict[str, Any]):
        super().__init__(message)
        self.reason_code = reason_code
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"error": "model_plane_unavailable", "reason_code": self.reason_code, **self.detail}


class ModelPlaneRouterService:
    """Singleton-style router; call ``reset_for_tests()`` between pytest cases."""

    _instance: ModelPlaneRouterService | None = None
    _instance_key: tuple[Any, ...] | None = None

    def __init__(self, settings: Settings, *, http_client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client_owned = http_client is None
        self._http = http_client or httpx.Client()
        self._primary_cb = _CircuitBreaker()
        self._secondary_cb = _CircuitBreaker()
        self._last_primary: ProbeResult = ProbeResult(ok=False)
        self._last_secondary: ProbeResult = ProbeResult(ok=False)
        self._last_secondary_ready_ok: bool | None = None
        self._last_probe_at: float | None = None
        self._last_selection_reason: str = ""
        self._lock_monotonic = time.monotonic

    @classmethod
    def get_or_create(cls, settings: Settings, *, http_client: httpx.Client | None = None) -> ModelPlaneRouterService:
        key = (
            settings.model_router_base_url,
            settings.model_router_secondary_base_url,
            settings.model_plane_secondary_enabled,
            settings.model_plane_connect_timeout_sec,
            settings.model_plane_read_timeout_sec,
            settings.model_plane_probe_retries,
            settings.model_plane_circuit_breaker_threshold,
            settings.model_plane_circuit_breaker_ttl_sec,
            settings.model_plane_secondary_ready_url,
            settings.model_plane_tcp_probe_enabled,
            id(http_client) if http_client is not None else None,
        )
        if cls._instance is None or cls._instance_key != key:
            if cls._instance is not None and cls._instance._client_owned:
                cls._instance._http.close()
            cls._instance = cls(settings, http_client=http_client)
            cls._instance_key = key
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        if cls._instance is not None and cls._instance._client_owned:
            cls._instance._http.close()
        cls._instance = None
        cls._instance_key = None

    def close(self) -> None:
        if self._client_owned:
            self._http.close()

    def _now(self) -> float:
        return self._lock_monotonic()

    def _tcp_check(self, base_url: str) -> bool:
        host, port = _parse_host_port(base_url)
        conn_timeout = float(self._settings.model_plane_connect_timeout_sec)
        try:
            with socket.create_connection((host, port), timeout=conn_timeout):
                return True
        except OSError:
            return False

    def _http_tags_probe(self, base_url: str) -> tuple[bool, str | None]:
        base = _normalize_base(base_url)
        url = f"{base}/api/tags"
        timeout = (
            float(self._settings.model_plane_connect_timeout_sec),
            float(self._settings.model_plane_read_timeout_sec),
        )
        try:
            r = self._http.get(url, timeout=timeout)
            if r.status_code != 200:
                return False, f"http_{r.status_code}"
            json.loads(r.text)  # validate JSON
            return True, None
        except Exception as e:
            return False, type(e).__name__

    def _run_probe_with_retries(self, base_url: str) -> ProbeResult:
        retries = max(0, int(self._settings.model_plane_probe_retries))
        total_attempts = 1 + retries
        last_err = "probe_failed"
        for attempt in range(total_attempts):
            if attempt > 0:
                _backoff_sleep(attempt - 1)
            t0 = time.perf_counter()
            if self._settings.model_plane_tcp_probe_enabled and not self._tcp_check(base_url):
                last_err = "tcp_connect_failed"
                continue
            ok, err = self._http_tags_probe(base_url)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if ok:
                return ProbeResult(ok=True, latency_ms=round(elapsed_ms, 3), retry_count=attempt)
            last_err = err or "http_probe_failed"
        return ProbeResult(ok=False, retry_count=retries, error=last_err)

    def probe_primary(self) -> ProbeResult:
        base = _normalize_base(self._settings.model_router_base_url)
        self._last_probe_at = time.time()
        if not base:
            self._last_primary = ProbeResult(ok=False, error="primary_not_configured")
            return self._last_primary
        now = self._now()
        if self._primary_cb.is_open(now):
            self._last_primary = ProbeResult(ok=False, error="circuit_open")
            return self._last_primary
        res = self._run_probe_with_retries(base)
        self._last_primary = res
        if res.ok:
            self._primary_cb.record_success()
        else:
            self._primary_cb.record_failure(
                threshold=self._settings.model_plane_circuit_breaker_threshold,
                ttl_sec=self._settings.model_plane_circuit_breaker_ttl_sec,
                now=now,
            )
        return res

    def probe_secondary(self) -> ProbeResult:
        self._last_probe_at = time.time()
        base = _normalize_base(self._settings.model_router_secondary_base_url)
        if not base:
            self._last_secondary = ProbeResult(ok=False, error="secondary_not_configured")
            return self._last_secondary
        now = self._now()
        if self._secondary_cb.is_open(now):
            self._last_secondary = ProbeResult(ok=False, error="circuit_open")
            return self._last_secondary
        res = self._run_probe_with_retries(base)
        self._last_secondary = res
        if res.ok:
            self._secondary_cb.record_success()
        else:
            self._secondary_cb.record_failure(
                threshold=self._settings.model_plane_circuit_breaker_threshold,
                ttl_sec=self._settings.model_plane_circuit_breaker_ttl_sec,
                now=now,
            )
        return res

    def _read_secondary_ready(self) -> bool | None:
        """None = skip; True/False = enforced."""
        raw = (self._settings.model_plane_secondary_ready_url or "").strip()
        if not raw:
            return None
        timeout = (
            float(self._settings.model_plane_connect_timeout_sec),
            float(self._settings.model_plane_read_timeout_sec),
        )
        try:
            r = self._http.get(raw, timeout=timeout)
            if r.status_code != 200:
                self._last_secondary_ready_ok = False
                return False
            data = r.json()
            accept = data.get("accept_inference")
            ok = accept is True
            self._last_secondary_ready_ok = ok
            return ok
        except Exception:
            self._last_secondary_ready_ok = False
            return False

    def is_secondary_eligible(self) -> bool:
        if not self._settings.model_plane_secondary_enabled:
            return False
        sec_base = _normalize_base(self._settings.model_router_secondary_base_url)
        if not sec_base:
            return False
        now = self._now()
        if self._secondary_cb.is_open(now):
            return False
        if not self._last_secondary.ok:
            return False
        ready = self._read_secondary_ready()
        if ready is False:
            return False
        return True

    def select_endpoint(
        self,
        request_type: ModelPlaneRequestType | str,
        *,
        prefer_secondary: bool = False,
        session: Session | None = None,
        directive_id: Any = None,
        project_id: Any = None,
        workspace_id: Any = None,
        correlation_id: Any = None,
    ) -> SelectedEndpoint:
        """Choose model plane. Default: primary. Secondary only when eligible *and* ``prefer_secondary``."""
        rt = request_type.value if isinstance(request_type, ModelPlaneRequestType) else str(request_type)
        primary_base = _normalize_base(self._settings.model_router_base_url)
        secondary_base = _normalize_base(self._settings.model_router_secondary_base_url)

        if not primary_base:
            self._last_selection_reason = ModelPlaneReasonCode.PRIMARY_UNAVAILABLE.value
            self._emit_audit(
                session,
                selected_endpoint="",
                plane="none",
                reason_code=ModelPlaneReasonCode.PRIMARY_UNAVAILABLE.value,
                request_type=rt,
                health_primary_ok=False,
                health_secondary_ok=False,
                latency_ms_primary=None,
                latency_ms_secondary=None,
                retry_count_probe=max(self._last_primary.retry_count, self._last_secondary.retry_count),
                directive_id=directive_id,
                project_id=project_id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
            )
            raise ModelPlaneUnavailableError(
                reason_code=ModelPlaneReasonCode.PRIMARY_UNAVAILABLE.value,
                message="model_router_base_url is not configured",
                detail={"request_type": rt},
            )

        now = self._now()
        if self._primary_cb.is_open(now):
            if secondary_base:
                self.probe_secondary()
            self._last_selection_reason = ModelPlaneReasonCode.PRIMARY_CIRCUIT_OPEN.value
            self._emit_audit(
                session,
                selected_endpoint=primary_base,
                plane="none",
                reason_code=ModelPlaneReasonCode.PRIMARY_CIRCUIT_OPEN.value,
                request_type=rt,
                health_primary_ok=False,
                health_secondary_ok=bool(secondary_base and self._last_secondary.ok),
                latency_ms_primary=self._last_primary.latency_ms,
                latency_ms_secondary=self._last_secondary.latency_ms if secondary_base else None,
                retry_count_probe=self._last_primary.retry_count,
                directive_id=directive_id,
                project_id=project_id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
            )
            raise ModelPlaneUnavailableError(
                reason_code=ModelPlaneReasonCode.PRIMARY_CIRCUIT_OPEN.value,
                message="primary model plane circuit breaker open",
                detail={"request_type": rt},
            )

        p_res = self.probe_primary()
        health_p = p_res.ok
        lat_p = p_res.latency_ms
        if not health_p:
            if secondary_base:
                self.probe_secondary()
            self._last_selection_reason = ModelPlaneReasonCode.PRIMARY_UNAVAILABLE.value
            self._emit_audit(
                session,
                selected_endpoint=primary_base,
                plane="none",
                reason_code=ModelPlaneReasonCode.PRIMARY_UNAVAILABLE.value,
                request_type=rt,
                health_primary_ok=False,
                health_secondary_ok=bool(secondary_base and self._last_secondary.ok),
                latency_ms_primary=lat_p,
                latency_ms_secondary=self._last_secondary.latency_ms if secondary_base else None,
                retry_count_probe=p_res.retry_count,
                directive_id=directive_id,
                project_id=project_id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
            )
            raise ModelPlaneUnavailableError(
                reason_code=ModelPlaneReasonCode.PRIMARY_UNAVAILABLE.value,
                message="primary model plane probe failed",
                detail={"request_type": rt, "error": p_res.error},
            )

        s_res = ProbeResult(ok=False)
        if secondary_base:
            s_res = self.probe_secondary()

        secondary_reason = ModelPlaneReasonCode.PRIMARY_DEFAULT.value
        if not secondary_base:
            secondary_reason = ModelPlaneReasonCode.SECONDARY_SKIPPED_NOT_CONFIGURED.value
        elif not self._settings.model_plane_secondary_enabled:
            secondary_reason = ModelPlaneReasonCode.SECONDARY_SKIPPED_DISABLED.value
        elif self._secondary_cb.is_open(self._now()):
            secondary_reason = ModelPlaneReasonCode.SECONDARY_SKIPPED_CIRCUIT_OPEN.value
        elif not s_res.ok:
            secondary_reason = ModelPlaneReasonCode.SECONDARY_SKIPPED_UNHEALTHY.value
        else:
            ready = self._read_secondary_ready()
            if ready is False:
                secondary_reason = ModelPlaneReasonCode.SECONDARY_SKIPPED_READY_REJECTED.value
            elif prefer_secondary and self.is_secondary_eligible():
                sel = SelectedEndpoint(
                    base_url=secondary_base,
                    plane="secondary",
                    reason_code=ModelPlaneReasonCode.SECONDARY_SELECTED.value,
                )
                self._last_selection_reason = sel.reason_code
                self._emit_audit(
                    session,
                    selected_endpoint=secondary_base,
                    plane="secondary",
                    reason_code=sel.reason_code,
                    request_type=rt,
                    health_primary_ok=True,
                    health_secondary_ok=True,
                    latency_ms_primary=lat_p,
                    latency_ms_secondary=s_res.latency_ms,
                    retry_count_probe=max(p_res.retry_count, s_res.retry_count),
                    directive_id=directive_id,
                    project_id=project_id,
                    workspace_id=workspace_id,
                    correlation_id=correlation_id,
                )
                return sel

        sel = SelectedEndpoint(
            base_url=primary_base,
            plane="primary",
            reason_code=ModelPlaneReasonCode.PRIMARY_DEFAULT.value,
        )
        self._last_selection_reason = f"{sel.reason_code};{secondary_reason}"
        self._emit_audit(
            session,
            selected_endpoint=primary_base,
            plane="primary",
            reason_code=sel.reason_code,
            request_type=rt,
            health_primary_ok=True,
            health_secondary_ok=bool(secondary_base and self._last_secondary.ok),
            latency_ms_primary=lat_p,
            latency_ms_secondary=self._last_secondary.latency_ms if secondary_base else None,
            retry_count_probe=max(p_res.retry_count, s_res.retry_count if secondary_base else 0),
            secondary_skip_reason=secondary_reason,
            directive_id=directive_id,
            project_id=project_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
        )
        return sel

    def _emit_audit(
        self,
        session: Session | None,
        *,
        selected_endpoint: str,
        plane: str,
        reason_code: str,
        request_type: str,
        health_primary_ok: bool,
        health_secondary_ok: bool,
        latency_ms_primary: float | None,
        latency_ms_secondary: float | None,
        retry_count_probe: int,
        directive_id: Any = None,
        project_id: Any = None,
        workspace_id: Any = None,
        correlation_id: Any = None,
        secondary_skip_reason: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "schema": AUDIT_SCHEMA,
            "selected_endpoint": selected_endpoint,
            "plane": plane,
            "reason_code": reason_code,
            "request_type": request_type,
            "health_primary_ok": health_primary_ok,
            "health_secondary_ok": health_secondary_ok,
            "latency_ms_primary": latency_ms_primary,
            "latency_ms_secondary": latency_ms_secondary,
            "retry_count_probe": retry_count_probe,
        }
        if correlation_id is not None:
            payload["correlation_id"] = str(correlation_id)
        if directive_id is not None:
            payload["directive_id"] = str(directive_id)
        if secondary_skip_reason:
            payload["secondary_skip_reason"] = secondary_skip_reason
        if session is None:
            return
        def _uid(v: Any) -> uuid.UUID | None:
            if v is None:
                return None
            return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))

        AuditRepository(session).record(
            event_type=AuditEventType.MODEL_ROUTING_DECISION,
            event_payload=payload,
            actor_type=AuditActorType.SYSTEM,
            actor_id="trident-model-plane-router",
            workspace_id=_uid(workspace_id),
            project_id=_uid(project_id),
            directive_id=_uid(directive_id),
        )

    def call_model(
        self,
        route: ModelPlaneHttpRoute | str,
        payload: dict[str, Any],
        *,
        request_type: ModelPlaneRequestType | str = ModelPlaneRequestType.CHAT,
        prefer_secondary: bool = False,
        session: Session | None = None,
        directive_id: Any = None,
        project_id: Any = None,
        workspace_id: Any = None,
        correlation_id: Any = None,
    ) -> dict[str, Any]:
        sel = self.select_endpoint(
            request_type,
            prefer_secondary=prefer_secondary,
            session=session,
            directive_id=directive_id,
            project_id=project_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
        )
        key = route.value if isinstance(route, ModelPlaneHttpRoute) else str(route)
        path = _ROUTE_PATHS.get(key)
        if path is None:
            raise ValueError(f"unknown_route:{key}")
        url = f"{_normalize_base(sel.base_url)}{path}"
        rt = float(self._settings.model_plane_request_timeout_sec)
        try:
            r = self._http.post(url, json=payload, timeout=rt)
            if r.status_code >= 400:
                now = self._now()
                if sel.plane == "primary":
                    self._primary_cb.record_failure(
                        threshold=self._settings.model_plane_circuit_breaker_threshold,
                        ttl_sec=self._settings.model_plane_circuit_breaker_ttl_sec,
                        now=now,
                    )
                else:
                    self._secondary_cb.record_failure(
                        threshold=self._settings.model_plane_circuit_breaker_threshold,
                        ttl_sec=self._settings.model_plane_circuit_breaker_ttl_sec,
                        now=now,
                    )
                raise ModelPlaneUnavailableError(
                    reason_code="MODEL_CALL_HTTP_ERROR",
                    message=f"model plane returned {r.status_code}",
                    detail={"status_code": r.status_code, "body_preview": r.text[:512]},
                )
            return dict(r.json())
        except ModelPlaneUnavailableError:
            raise
        except Exception as e:
            now = self._now()
            if sel.plane == "primary":
                self._primary_cb.record_failure(
                    threshold=self._settings.model_plane_circuit_breaker_threshold,
                    ttl_sec=self._settings.model_plane_circuit_breaker_ttl_sec,
                    now=now,
                )
            else:
                self._secondary_cb.record_failure(
                    threshold=self._settings.model_plane_circuit_breaker_threshold,
                    ttl_sec=self._settings.model_plane_circuit_breaker_ttl_sec,
                    now=now,
                )
            raise ModelPlaneUnavailableError(
                reason_code="MODEL_CALL_FAILED",
                message=str(e),
                detail={"plane": sel.plane, "error": type(e).__name__},
            ) from e

    def refresh_probes(self) -> None:
        """Refresh probe cache for status endpoint."""
        self.probe_primary()
        if _normalize_base(self._settings.model_router_secondary_base_url):
            self.probe_secondary()

    def status_snapshot(self) -> dict[str, Any]:
        secondary_cfg = bool(_normalize_base(self._settings.model_router_secondary_base_url))
        eligible = self.is_secondary_eligible() if secondary_cfg and self._settings.model_plane_secondary_enabled else False
        return {
            "primary_healthy": self._last_primary.ok,
            "secondary_configured": secondary_cfg,
            "secondary_healthy": self._last_secondary.ok if secondary_cfg else False,
            "secondary_eligible": eligible,
            "last_selection_reason": self._last_selection_reason,
            "last_probe_at": self._last_probe_at,
            "secondary_ready_signal_ok": self._last_secondary_ready_ok,
        }
