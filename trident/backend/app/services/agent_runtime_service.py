"""AgentRuntimeService — governed Engineer agent runtime (TRIDENT_AGENT_RUNTIME_001).

Single-agent loop: directive context → governed model call → structured JSON parse
→ PatchProposal creation via existing PatchProposalService.

Constraints (enforced here, not caller-side):
- Only ENGINEER role in this directive.
- Directive must be ISSUED and not CLOSED.
- Model calls go through existing ModelRouterService only.
- No direct Ollama / provider calls.
- No file writes, no patch execution, no validation, no signoff.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.directive import Directive
from app.models.enums import AgentRole, AuditActorType, AuditEventType, DirectiveStatus
from app.services.agent_context_retriever import AgentContextRetriever, RetrievedContext
from app.model_router.model_router_service import ModelRouterResult, ModelRouterService
from app.repositories.audit_repository import AuditRepository
from app.repositories.task_ledger_repository import TaskLedgerRepository
from app.schemas.proposal_schemas import PatchProposalCreateRequest
from app.services.patch_proposal_service import DirectiveMismatchError, PatchProposalService


# ── Structured agent output ───────────────────────────────────────────────────

@dataclass
class AgentPatchOutput:
    title: str
    summary: str
    files_changed: list[dict[str, Any]]
    unified_diff: str


class AgentOutputParseError(ValueError):
    """Raised when the model response cannot be parsed into a valid patch proposal."""
    pass


class AgentRuntimeBlockedError(ValueError):
    """Raised when guardrails block the agent run."""
    pass


_PROHIBITED_CHANGE_TYPES = frozenset({"delete"})
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _extract_json(text: str) -> str:
    """Extract JSON from model response — strip markdown fences if present."""
    match = _JSON_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    # Try raw — the text may be plain JSON
    stripped = text.strip()
    if stripped.startswith("{"):
        return stripped
    raise AgentOutputParseError("no_json_found_in_response")


def _parse_agent_output(response_text: str) -> AgentPatchOutput:
    raw = _extract_json(response_text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AgentOutputParseError(f"json_decode_error:{e}") from e

    if not isinstance(data, dict):
        raise AgentOutputParseError("output_must_be_json_object")

    title = data.get("title", "").strip()
    summary = data.get("summary", "").strip()
    files_changed = data.get("files_changed")
    unified_diff = data.get("unified_diff", "")

    if not title:
        raise AgentOutputParseError("missing_field:title")
    if not summary:
        raise AgentOutputParseError("missing_field:summary")
    if not isinstance(files_changed, list) or len(files_changed) == 0:
        raise AgentOutputParseError("files_changed_empty_or_missing")

    for f in files_changed:
        if not isinstance(f, dict):
            raise AgentOutputParseError("files_changed_entry_must_be_object")
        path = str(f.get("path", "")).strip()
        change_type = str(f.get("change_type", "update")).lower()
        content = f.get("content")

        if not path:
            raise AgentOutputParseError("empty_file_path")
        if path.startswith("/"):
            raise AgentOutputParseError(f"absolute_path_forbidden:{path[:80]}")
        if ".." in path or "\\" in path:
            raise AgentOutputParseError(f"path_traversal_forbidden:{path[:80]}")
        if change_type in _PROHIBITED_CHANGE_TYPES:
            raise AgentOutputParseError(f"delete_operation_not_supported:{path[:80]}")
        if content is None or not isinstance(content, str):
            raise AgentOutputParseError(f"missing_or_binary_content:{path[:80]}")

    return AgentPatchOutput(
        title=title,
        summary=summary,
        files_changed=files_changed,
        unified_diff=str(unified_diff) if unified_diff else "",
    )


# ── Prompt construction ───────────────────────────────────────────────────────

def _build_engineer_prompt(
    directive: Directive,
    instruction: str | None = None,
    execution_context: str | None = None,
    context_block: str | None = None,
) -> str:
    lines = ["You are the Trident Engineer agent."]

    # Inject project context first (when available) so model grounds in repo reality
    if context_block:
        lines += [context_block, ""]

    lines += [
        f"[DIRECTIVE]",
        f"Directive ID: {directive.id}",
        f"Directive title: {directive.title}",
        "",
        "[INSTRUCTION]",
    ]
    if instruction:
        lines.append(instruction)
    lines += [
        "",
        "Your task: produce a patch proposal as structured JSON.",
        "IMPORTANT: If project context was provided above, use real file paths and code patterns from it.",
        "Match existing variable names, class names, and coding conventions.",
        "",
        "Output ONLY a JSON object with this exact structure:",
        '{',
        '  "title": "short descriptive title",',
        '  "summary": "explanation of what changes and why",',
        '  "files_changed": [',
        '    {"path": "relative/path/to/file.py", "change_type": "create|update", "content": "...full file content..."}',
        '  ],',
        '  "unified_diff": "optional unified diff string"',
        '}',
        "",
        "Rules:",
        "- Use actual file paths from the repository.",
        "- Paths must be relative (no leading /).",
        "- No delete operations.",
        "- Respond with ONLY the JSON object — no commentary before or after.",
    ]
    if execution_context:
        lines += ["", "Context:", execution_context]
    return "\n".join(lines)


# ── Runtime result ────────────────────────────────────────────────────────────

@dataclass
class AgentRunResult:
    patch_id: uuid.UUID
    title: str
    summary: str
    model_routing_trace: dict[str, Any]
    audit_event_ids: list[str]


# ── Service ───────────────────────────────────────────────────────────────────

class AgentRuntimeService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._audit = AuditRepository(db)

    def _get_directive(self, directive_id: uuid.UUID, project_id: uuid.UUID) -> Directive:
        d = self._db.get(Directive, directive_id)
        if d is None or d.project_id != project_id:
            raise AgentRuntimeBlockedError("directive_not_in_project")
        return d

    def _emit(
        self,
        event_type: AuditEventType,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> None:
        self._audit.record(
            event_type=event_type,
            event_payload=payload,
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{AgentRole.ENGINEER.value}:{user_id}",
            project_id=project_id,
            directive_id=directive_id,
        )

    def run_engineer(
        self,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        user_id: uuid.UUID,
        instruction: str | None = None,
        allowed_actions_from_state: dict[str, Any] | None = None,
        model_plane_router: Any = None,
    ) -> AgentRunResult:
        """Run the Engineer agent once. Validates pre-conditions, calls model, parses output, creates patch."""

        directive = self._get_directive(directive_id, project_id)

        # ── Guardrails ────────────────────────────────────────────────────────
        if directive.status == DirectiveStatus.CLOSED.value:
            raise AgentRuntimeBlockedError("directive_closed")
        if directive.status != DirectiveStatus.ISSUED.value:
            raise AgentRuntimeBlockedError(f"directive_not_issued:status={directive.status}")

        if allowed_actions_from_state is not None:
            create_patch = allowed_actions_from_state.get("create_patch", {})
            if not create_patch.get("allowed", True) is True:
                reason = create_patch.get("reason_code", "create_patch_not_allowed")
                raise AgentRuntimeBlockedError(reason)

        # ── Load task ledger ──────────────────────────────────────────────────
        ledger = TaskLedgerRepository(self._db).get_by_directive_id(directive_id)
        if ledger is None:
            raise AgentRuntimeBlockedError("task_ledger_not_found")

        # ── Emit STARTED ──────────────────────────────────────────────────────
        self._emit(
            AuditEventType.AGENT_RUN_STARTED,
            project_id=project_id,
            directive_id=directive_id,
            user_id=user_id,
            payload={
                "agent_role": AgentRole.ENGINEER.value,
                "directive_id": str(directive_id),
                "project_id": str(project_id),
                "instruction_provided": bool(instruction),
            },
        )
        self._db.flush()

        # ── Retrieve project context (RAG) ───────────────────────────────────
        retriever = AgentContextRetriever(self._settings)
        query = f"{directive.title} {instruction or ''}"
        ctx: RetrievedContext = retriever.retrieve(project_id=project_id, query_text=query)
        context_block = retriever.format_context_block(ctx) if ctx.context_used else None

        # ── Build prompt ──────────────────────────────────────────────────────
        prompt = _build_engineer_prompt(directive, instruction, context_block=context_block)

        # ── Model call (governed router) ──────────────────────────────────────
        model_svc = ModelRouterService(
            self._db,
            self._settings,
            model_plane_router=model_plane_router,
        )
        try:
            model_result: ModelRouterResult = model_svc.route(
                directive=directive,
                ledger=ledger,
                agent_role=AgentRole.ENGINEER,
                prompt=prompt,
            )
        except Exception as e:
            self._emit(
                AuditEventType.AGENT_RUN_FAILED,
                project_id=project_id,
                directive_id=directive_id,
                user_id=user_id,
                payload={
                    "agent_role": AgentRole.ENGINEER.value,
                    "reason_code": "model_router_error",
                    "detail": type(e).__name__,
                },
            )
            self._db.flush()
            raise AgentRuntimeBlockedError(f"model_router_error:{type(e).__name__}") from e

        routing_trace = model_result.as_trace_dict()
        correlation_id = routing_trace.get("token_optimization", {}).get("model_plane_correlation_id")

        # ── Parse output ──────────────────────────────────────────────────────
        try:
            output = _parse_agent_output(model_result.response_text)
        except AgentOutputParseError as e:
            self._emit(
                AuditEventType.AGENT_RUN_FAILED,
                project_id=project_id,
                directive_id=directive_id,
                user_id=user_id,
                payload={
                    "agent_role": AgentRole.ENGINEER.value,
                    "reason_code": "output_parse_error",
                    "parse_error": str(e),
                    "model_correlation_id": correlation_id,
                },
            )
            self._db.flush()
            raise

        # ── Create patch proposal ─────────────────────────────────────────────
        files_for_patch = {
            "files": [
                {"path": f["path"], "content": f["content"], "change_type": f.get("change_type", "update")}
                for f in output.files_changed
            ]
        }
        patch_req = PatchProposalCreateRequest(
            title=output.title,
            summary=output.summary,
            files_changed=files_for_patch,
            unified_diff=output.unified_diff or None,
            proposed_by_agent_role=AgentRole.ENGINEER.value,
        )
        patch_svc = PatchProposalService(self._db)
        patch_detail = patch_svc.create(project_id, directive_id, user_id, patch_req)

        # ── Emit COMPLETED ────────────────────────────────────────────────────
        self._emit(
            AuditEventType.AGENT_RUN_COMPLETED,
            project_id=project_id,
            directive_id=directive_id,
            user_id=user_id,
            payload={
                "agent_role": AgentRole.ENGINEER.value,
                "patch_id": str(patch_detail.id),
                "title": output.title,
                "file_count": len(output.files_changed),
                "model_routing_decision": model_result.decision,
                "model_correlation_id": correlation_id,
                # RAG context audit (AGENT_CONTEXT_001)
                "context_used": ctx.context_used,
                "context_chunk_count": ctx.chunk_count,
                "context_files_used": ctx.files_used,
                "context_warning": ctx.warning,
            },
        )
        self._db.flush()

        return AgentRunResult(
            patch_id=patch_detail.id,
            title=output.title,
            summary=output.summary,
            model_routing_trace=routing_trace,
            audit_event_ids=[],
        )
