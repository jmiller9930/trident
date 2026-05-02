"""ReviewerRuntimeService — governed Reviewer agent runtime (TRIDENT_AGENT_REVIEWER_001).

Produces a structured review recommendation for a PROPOSED patch.
Never mutates patch status. Recommendation must be acted on by a human.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.directive import Directive
from app.models.enums import AgentRole, AuditActorType, AuditEventType, DirectiveStatus
from app.services.agent_context_retriever import AgentContextRetriever, RetrievedContext
from app.model_router.model_router_service import ModelRouterResult, ModelRouterService
from app.models.patch_proposal import PatchProposal, PatchProposalStatus
from app.models.patch_review import PatchReview, ReviewerRecommendation
from app.repositories.audit_repository import AuditRepository
from app.repositories.task_ledger_repository import TaskLedgerRepository


# ── Structured output ────────────────────────────────────────────────────────

_VALID_RECOMMENDATIONS = frozenset(r.value for r in ReviewerRecommendation)
_VALID_SEVERITIES = frozenset({"INFO", "WARNING", "ERROR", "BLOCKING"})
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


@dataclass
class ReviewFinding:
    severity: str
    message: str
    path: str | None = None
    suggested_action: str | None = None


@dataclass
class ReviewerOutput:
    recommendation: str
    confidence: float
    summary: str
    findings: list[ReviewFinding] = field(default_factory=list)


class ReviewerOutputParseError(ValueError):
    pass


class ReviewerRuntimeBlockedError(ValueError):
    pass


def _extract_json(text: str) -> str:
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    stripped = text.strip()
    if stripped.startswith("{"):
        return stripped
    raise ReviewerOutputParseError("no_json_found_in_response")


def _parse_reviewer_output(response_text: str) -> ReviewerOutput:
    raw = _extract_json(response_text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ReviewerOutputParseError(f"json_decode_error:{e}") from e

    if not isinstance(data, dict):
        raise ReviewerOutputParseError("output_must_be_json_object")

    rec = str(data.get("recommendation", "")).strip().upper()
    if not rec:
        raise ReviewerOutputParseError("missing_field:recommendation")
    if rec not in _VALID_RECOMMENDATIONS:
        raise ReviewerOutputParseError(f"invalid_recommendation:{rec}")

    raw_conf = data.get("confidence")
    if raw_conf is None:
        raise ReviewerOutputParseError("missing_field:confidence")
    try:
        confidence = float(raw_conf)
    except (TypeError, ValueError) as e:
        raise ReviewerOutputParseError("confidence_must_be_number") from e
    if not 0.0 <= confidence <= 1.0:
        raise ReviewerOutputParseError(f"confidence_out_of_range:{confidence}")

    summary = str(data.get("summary", "")).strip()
    if not summary:
        raise ReviewerOutputParseError("missing_field:summary")

    raw_findings = data.get("findings", [])
    if not isinstance(raw_findings, list):
        raise ReviewerOutputParseError("findings_must_be_array")

    findings: list[ReviewFinding] = []
    for f in raw_findings:
        if not isinstance(f, dict):
            raise ReviewerOutputParseError("finding_must_be_object")
        sev = str(f.get("severity", "INFO")).upper()
        if sev not in _VALID_SEVERITIES:
            raise ReviewerOutputParseError(f"invalid_finding_severity:{sev}")
        msg = str(f.get("message", "")).strip()
        if not msg:
            raise ReviewerOutputParseError("finding_missing_message")
        path = f.get("path")
        if path is not None:
            path = str(path).strip()
            if path.startswith("/"):
                raise ReviewerOutputParseError(f"finding_absolute_path:{path[:80]}")
            if ".." in path or "\\" in path:
                raise ReviewerOutputParseError(f"finding_traversal_path:{path[:80]}")
        findings.append(ReviewFinding(
            severity=sev,
            message=msg,
            path=path or None,
            suggested_action=f.get("suggested_action"),
        ))

    # REJECT/NEEDS_CHANGES should have at least one finding
    if rec in ("REJECT", "NEEDS_CHANGES") and not findings:
        raise ReviewerOutputParseError(f"findings_required_for_recommendation:{rec}")

    return ReviewerOutput(
        recommendation=rec,
        confidence=confidence,
        summary=summary,
        findings=findings,
    )


# ── Prompt ───────────────────────────────────────────────────────────────────

def _build_reviewer_prompt(
    directive: Directive,
    patch: PatchProposal,
    instruction: str | None = None,
    context_block: str | None = None,
) -> str:
    files_summary = ""
    fc = patch.files_changed
    if isinstance(fc, dict) and "files" in fc:
        paths = [f.get("path", "?") for f in fc["files"]]
        files_summary = f"Files in patch: {', '.join(paths[:10])}"
    elif isinstance(fc, list):
        paths = [f.get("path", "?") for f in fc[:10]]
        files_summary = f"Files in patch: {', '.join(paths)}"

    lines = ["You are the Trident Reviewer agent."]

    # Inject project context first (when available)
    if context_block:
        lines += [context_block, ""]

    lines += [
        "[PATCH UNDER REVIEW]",
        f"Directive ID: {directive.id}",
        f"Directive title: {directive.title}",
        f"Patch ID: {patch.id}",
        f"Patch title: {patch.title}",
        f"Patch summary: {patch.summary or 'none'}",
        files_summary,
        "",
        "Your task: review this patch proposal against the [PROJECT CONTEXT] above.",
        "CRITICAL: If the patch uses wrong variable names, incorrect key names, or contradicts",
        "the code patterns shown in the context, flag it as NEEDS_CHANGES or REJECT.",
        "",
        "Output ONLY a JSON object:",
        '{',
        '  "recommendation": "ACCEPT|REJECT|NEEDS_CHANGES",',
        '  "confidence": 0.85,',
        '  "summary": "brief review summary",',
        '  "findings": [',
        '    {"severity": "INFO|WARNING|ERROR|BLOCKING", "message": "...", "path": "optional/path", "suggested_action": "..."}',
        '  ]',
        '}',
        "",
        "Rules:",
        "- Compare patch content to the project context. Flag mismatches.",
        "- findings paths must be relative (no leading /).",
        "- REJECT and NEEDS_CHANGES require at least one finding.",
        "- Respond with ONLY the JSON object.",
    ]
    if instruction:
        lines.insert(len(lines) - 10, f"Reviewer instruction: {instruction}")
    return "\n".join(lines)


# ── Service ──────────────────────────────────────────────────────────────────

@dataclass
class ReviewRunResult:
    review_id: uuid.UUID
    recommendation: str
    confidence: float
    summary: str
    findings: list[dict[str, Any]]
    model_routing_trace: dict[str, Any]


class ReviewerRuntimeService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._audit = AuditRepository(db)

    def _get_directive(self, directive_id: uuid.UUID, project_id: uuid.UUID) -> Directive:
        d = self._db.get(Directive, directive_id)
        if d is None or d.project_id != project_id:
            raise ReviewerRuntimeBlockedError("directive_not_in_project")
        return d

    def _get_patch(self, patch_id: uuid.UUID, directive_id: uuid.UUID, project_id: uuid.UUID) -> PatchProposal:
        p = self._db.get(PatchProposal, patch_id)
        if p is None or p.directive_id != directive_id or p.project_id != project_id:
            raise ReviewerRuntimeBlockedError("patch_not_in_directive")
        return p

    def _emit(self, event_type: AuditEventType, *, project_id: uuid.UUID,
              directive_id: uuid.UUID, user_id: uuid.UUID | None, payload: dict[str, Any]) -> None:
        self._audit.record(
            event_type=event_type,
            event_payload=payload,
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{AgentRole.REVIEWER.value}:{user_id}",
            project_id=project_id,
            directive_id=directive_id,
        )

    def run_reviewer(
        self,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        patch_id: uuid.UUID,
        user_id: uuid.UUID,
        instruction: str | None = None,
        model_plane_router: Any = None,
    ) -> ReviewRunResult:
        directive = self._get_directive(directive_id, project_id)
        if directive.status == DirectiveStatus.CLOSED.value:
            raise ReviewerRuntimeBlockedError("directive_closed")
        if directive.status != DirectiveStatus.ISSUED.value:
            raise ReviewerRuntimeBlockedError(f"directive_not_issued:status={directive.status}")

        patch = self._get_patch(patch_id, directive_id, project_id)
        if patch.status != PatchProposalStatus.PROPOSED.value:
            raise ReviewerRuntimeBlockedError(f"patch_not_proposed:status={patch.status}")

        ledger = TaskLedgerRepository(self._db).get_by_directive_id(directive_id)
        if ledger is None:
            raise ReviewerRuntimeBlockedError("task_ledger_not_found")

        self._emit(
            AuditEventType.AGENT_REVIEW_STARTED,
            project_id=project_id, directive_id=directive_id, user_id=user_id,
            payload={
                "agent_role": AgentRole.REVIEWER.value,
                "directive_id": str(directive_id),
                "patch_id": str(patch_id),
                "project_id": str(project_id),
            },
        )
        self._db.flush()

        # ── Retrieve project context (RAG) ─────────────────────────────────────
        retriever = AgentContextRetriever(self._settings)
        query = f"{directive.title} {patch.title or ''} {instruction or ''}"
        ctx: RetrievedContext = retriever.retrieve(project_id=project_id, query_text=query)
        context_block = retriever.format_context_block(ctx) if ctx.context_used else None

        prompt = _build_reviewer_prompt(directive, patch, instruction, context_block=context_block)
        model_svc = ModelRouterService(self._db, self._settings, model_plane_router=model_plane_router)
        try:
            model_result: ModelRouterResult = model_svc.route(
                directive=directive,
                ledger=ledger,
                agent_role=AgentRole.REVIEWER,
                prompt=prompt,
            )
        except Exception as e:
            self._emit(
                AuditEventType.AGENT_REVIEW_FAILED,
                project_id=project_id, directive_id=directive_id, user_id=user_id,
                payload={"agent_role": AgentRole.REVIEWER.value, "patch_id": str(patch_id),
                         "reason_code": "model_router_error", "detail": type(e).__name__},
            )
            self._db.flush()
            raise ReviewerRuntimeBlockedError(f"model_router_error:{type(e).__name__}") from e

        routing_trace = model_result.as_trace_dict()
        correlation_id = routing_trace.get("token_optimization", {}).get("model_plane_correlation_id")

        try:
            output = _parse_reviewer_output(model_result.response_text)
        except ReviewerOutputParseError as e:
            self._emit(
                AuditEventType.AGENT_REVIEW_FAILED,
                project_id=project_id, directive_id=directive_id, user_id=user_id,
                payload={"agent_role": AgentRole.REVIEWER.value, "patch_id": str(patch_id),
                         "reason_code": "output_parse_error", "parse_error": str(e),
                         "model_correlation_id": correlation_id},
            )
            self._db.flush()
            raise

        # Sanitised trace (no raw file content)
        safe_trace = {k: v for k, v in routing_trace.items() if k != "signal_breakdown"}

        review = PatchReview(
            project_id=project_id,
            directive_id=directive_id,
            patch_id=patch_id,
            reviewer_agent_role=AgentRole.REVIEWER.value,
            recommendation=output.recommendation,
            confidence=output.confidence,
            summary=output.summary,
            findings_json=[
                {"severity": f.severity, "message": f.message,
                 "path": f.path, "suggested_action": f.suggested_action}
                for f in output.findings
            ],
            model_routing_trace_json=safe_trace,
            created_by_user_id=user_id,
        )
        self._db.add(review)
        self._db.flush()

        self._emit(
            AuditEventType.AGENT_REVIEW_COMPLETED,
            project_id=project_id, directive_id=directive_id, user_id=user_id,
            payload={
                "agent_role": AgentRole.REVIEWER.value,
                "patch_id": str(patch_id),
                "review_id": str(review.id),
                "recommendation": output.recommendation,
                "confidence": output.confidence,
                "finding_count": len(output.findings),
                "model_correlation_id": correlation_id,
                # RAG context audit (AGENT_CONTEXT_001)
                "context_used": ctx.context_used,
                "context_chunk_count": ctx.chunk_count,
                "context_files_used": ctx.files_used,
                "context_warning": ctx.warning,
            },
        )
        self._db.flush()

        return ReviewRunResult(
            review_id=review.id,
            recommendation=output.recommendation,
            confidence=output.confidence,
            summary=output.summary,
            findings=[{"severity": f.severity, "message": f.message,
                       "path": f.path, "suggested_action": f.suggested_action}
                      for f in output.findings],
            model_routing_trace=safe_trace,
        )
