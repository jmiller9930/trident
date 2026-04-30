"""Subsystem router HTTP surface — single decision endpoint (100G)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.router.router_service import RouterService
from app.schemas.router import RouterRouteRequest, RouterRouteResponse

router = APIRouter()


def _map_validation_error(e: ValueError) -> HTTPException:
    code = str(e)
    if code in ("directive_not_found", "task_not_found"):
        return HTTPException(status_code=404, detail=code)
    if code in (
        "task_directive_mismatch",
        "intent_required",
        "invalid_agent_role",
    ):
        return HTTPException(status_code=400, detail=code)
    return HTTPException(status_code=400, detail=code)


@router.post("/route", response_model=RouterRouteResponse)
def router_decide(body: RouterRouteRequest, db: Session = Depends(get_db)) -> RouterRouteResponse:
    try:
        return RouterService(db).decide(body)
    except ValueError as e:
        raise _map_validation_error(e) from e
