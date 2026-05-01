from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.config.settings import Settings
from app.db.session import get_db, get_settings_dep
from app.model_router.budget import snapshot_usage_all
from app.model_router.health import model_router_health_snapshot
from app.services.model_router import ModelPlaneRouterService

router = APIRouter()

_REQUIRED_TABLES = frozenset(
    {
        "users",
        "workspaces",
        "projects",
        "directives",
        "task_ledger",
        "graph_states",
        "handoffs",
        "proof_objects",
        "audit_events",
        "file_locks",
        "memory_entries",
    }
)


@router.get("/model-router-status")
def model_router_status(cfg: Settings = Depends(get_settings_dep)) -> dict[str, object]:
    """FIX 005 — read-only visibility (audit-first complement); no 100G subsystem router fields."""
    return {
        "health": model_router_health_snapshot(settings=cfg),
        "external_usage_chars_by_directive": snapshot_usage_all(),
    }


@router.get("/model-plane-status")
def model_plane_status(cfg: Settings = Depends(get_settings_dep)) -> dict[str, object]:
    """MODEL_ROUTER_001 — primary/secondary plane health and last routing context (read-only)."""
    svc = ModelPlaneRouterService.get_or_create(cfg)
    svc.refresh_probes()
    return svc.status_snapshot()


@router.get("/schema-status")
def schema_status(db: Session = Depends(get_db)) -> dict[str, object]:
    bind = db.get_bind()
    insp = inspect(bind)
    names = set(insp.get_table_names())
    missing = sorted(_REQUIRED_TABLES - names)
    present = sorted(_REQUIRED_TABLES & names)
    return {
        "ok": len(missing) == 0,
        "required_table_count": len(_REQUIRED_TABLES),
        "tables_present": present,
        "tables_missing": missing,
    }
