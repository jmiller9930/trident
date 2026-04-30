from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends

from app.db.session import get_db

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
