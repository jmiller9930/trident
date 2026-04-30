"""FastAPI routes for MCP classify + execute (100F)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.mcp.mcp_service import MCPService
from app.schemas.mcp import MCPClassifyRequest, MCPClassifyResponse, MCPExecuteRequest, MCPExecuteResponse

router = APIRouter()


def _map_validation_error(e: ValueError) -> HTTPException:
    code = str(e)
    if code in ("directive_not_found", "task_not_found"):
        return HTTPException(status_code=404, detail=code)
    if code in ("task_directive_mismatch", "invalid_target", "command_required", "invalid_agent_role"):
        return HTTPException(status_code=400, detail=code)
    return HTTPException(status_code=400, detail=code)


@router.post("/classify", response_model=MCPClassifyResponse)
def mcp_classify(body: MCPClassifyRequest, db: Session = Depends(get_db)) -> MCPClassifyResponse:
    try:
        return MCPService(db).classify(body)
    except ValueError as e:
        raise _map_validation_error(e) from e


@router.post("/execute", response_model=MCPExecuteResponse)
def mcp_execute(body: MCPExecuteRequest, db: Session = Depends(get_db)) -> MCPExecuteResponse:
    try:
        out = MCPService(db).execute(body)
    except ValueError as e:
        raise _map_validation_error(e) from e
    if out.status == "rejected_high_unapproved":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "high_risk_not_approved",
                "proof_object_id": str(out.proof_object_id),
                "risk": out.risk,
            },
        )
    return out
