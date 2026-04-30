"""MCP orchestration — classify + simulated execute + receipts (100F)."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.mcp.adapters import local_adapter, ssh_adapter
from app.mcp.classifier import RiskLevel, classify_risk
from app.mcp.mcp_logger import MCPAuditLogger
from app.mcp.mcp_validator import normalize_target, resolve_context
from app.models.enums import ProofObjectType
from app.models.proof_object import ProofObject
from app.schemas.mcp import MCPClassifyRequest, MCPClassifyResponse, MCPExecuteRequest, MCPExecuteResponse


class MCPService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._log = MCPAuditLogger(session)

    def classify(self, body: MCPClassifyRequest) -> MCPClassifyResponse:
        _d, _ledger, _role = resolve_context(
            self._session,
            directive_id=body.directive_id,
            task_id=body.task_id,
            agent_role=body.agent_role,
            command=body.command,
            target=body.target,
        )
        risk, rationale = classify_risk(command=body.command)
        return MCPClassifyResponse(risk=risk.value, classification_rationale=rationale)

    def execute(self, body: MCPExecuteRequest) -> MCPExecuteResponse:
        directive, _ledger, role_val = resolve_context(
            self._session,
            directive_id=body.directive_id,
            task_id=body.task_id,
            agent_role=body.agent_role,
            command=body.command,
            target=body.target,
        )
        risk, rationale = classify_risk(command=body.command)
        target_norm = normalize_target(body.target)

        self._log.execution_requested(
            directive,
            task_id=body.task_id,
            agent_role=role_val,
            command=body.command,
            target=target_norm,
            risk=risk.value,
            rationale=rationale,
        )
        # Flush so MCP_EXECUTION_REQUESTED always precedes COMPLETED in audit ordering (Postgres tie-break on id/created_at).
        self._session.flush()

        if risk == RiskLevel.HIGH and not body.explicitly_approved:
            receipt = {
                "task_id": str(body.task_id),
                "directive_id": str(body.directive_id),
                "command": body.command[:500],
                "target": target_norm,
                "risk": risk.value,
                "explicitly_approved": False,
                "approved": False,
                "status": "rejected_high_unapproved",
                "simulated": True,
            }
            proof = ProofObject(
                directive_id=directive.id,
                proof_type=ProofObjectType.EXECUTION_LOG.value,
                proof_summary=json.dumps(receipt),
                proof_uri=None,
                proof_hash=None,
                created_by_agent_role=role_val,
            )
            self._session.add(proof)
            self._session.flush()

            self._log.execution_rejected(
                directive,
                task_id=body.task_id,
                agent_role=role_val,
                reason_code="high_risk_not_approved",
                detail={
                    "risk": risk.value,
                    "classification_rationale": rationale,
                    "target": target_norm,
                },
                proof_object_id=proof.id,
            )
            return MCPExecuteResponse(
                proof_object_id=proof.id,
                risk=risk.value,
                simulated=True,
                status="rejected_high_unapproved",
                explicitly_approved=False,
                adapter="none",
                stdout="",
                stderr="execution blocked: HIGH risk requires explicitly_approved=true",
                exit_code=-1,
            )

        if target_norm == "local":
            sim_out = local_adapter.simulate(command=body.command, target=target_norm)
        else:
            sim_out = ssh_adapter.simulate_stub(command=body.command, target=target_norm)

        receipt = {
            "task_id": str(body.task_id),
            "directive_id": str(directive.id),
            "command": body.command[:500],
            "target": target_norm,
            "risk": risk.value,
            "explicitly_approved": body.explicitly_approved,
            "approved": True,
            "status": "success",
            "simulated": True,
            "adapter": sim_out["adapter"],
            "stdout": sim_out["stdout"],
            "stderr": sim_out["stderr"],
            "exit_code": sim_out["exit_code"],
        }
        proof = ProofObject(
            directive_id=directive.id,
            proof_type=ProofObjectType.EXECUTION_LOG.value,
            proof_summary=json.dumps(receipt),
            proof_uri=None,
            proof_hash=None,
            created_by_agent_role=role_val,
        )
        self._session.add(proof)
        self._session.flush()

        summary_for_audit = {
            "risk": risk.value,
            "target": target_norm,
            "adapter": sim_out["adapter"],
            "exit_code": sim_out["exit_code"],
            "stdout_preview": str(sim_out["stdout"])[:300],
        }
        self._log.execution_completed(
            directive,
            task_id=body.task_id,
            agent_role=role_val,
            proof_object_id=proof.id,
            receipt_summary=summary_for_audit,
        )

        return MCPExecuteResponse(
            proof_object_id=proof.id,
            risk=risk.value,
            simulated=True,
            status="success",
            explicitly_approved=body.explicitly_approved,
            adapter=str(sim_out["adapter"]),
            stdout=str(sim_out["stdout"]),
            stderr=str(sim_out["stderr"]),
            exit_code=int(sim_out["exit_code"]),
        )
