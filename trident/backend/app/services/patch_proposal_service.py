"""PatchProposalService — governed review lifecycle for diff proposals (PATCH_001).

Rules:
- ACCEPTED and REJECTED patches are immutable.
- reject requires a non-empty reason.
- Only one ACCEPTED patch per directive (enforced at service level; future supersede flow handled separately).
- Proof object created on accept.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.git_provider.base import GitProvider
from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType, ProofObjectType
from app.models.patch_proposal import (
    PatchExecutionStatus,
    PatchProposal,
    PatchProposalStatus,
    _IMMUTABLE_STATUSES,
)
from app.models.proof_object import ProofObject
from app.repositories.audit_repository import AuditRepository
from app.schemas.git_schemas import GitPushFileItem, GitPushFilesRequest
from app.schemas.proposal_schemas import (
    PatchExecuteResponse,
    PatchProposalAcceptResponse,
    PatchProposalCreateRequest,
    PatchProposalDetail,
    PatchProposalListResponse,
    PatchProposalRejectRequest,
    PatchProposalRejectResponse,
    PatchProposalSummary,
)


class PatchImmutableError(ValueError):
    pass


class PatchAlreadyAcceptedError(ValueError):
    pass


class PatchAlreadyExecutedError(ValueError):
    pass


class PatchNotExecutableError(ValueError):
    pass


class PatchFileConversionError(ValueError):
    pass


class PatchNotFoundError(ValueError):
    pass


class DirectiveMismatchError(ValueError):
    pass


def _convert_files_changed(files_changed: dict | None) -> list[GitPushFileItem]:
    """Convert patch.files_changed into push-file payloads.

    Expected format: {path: str, content: str, change_type: "create"|"update"}
    OR legacy simplified format: {path: str} — rejected (no content).

    Rules:
    - Must have "path" and "content" keys.
    - change_type "delete" → rejected.
    - Absolute paths and traversal paths → rejected (service layer also checks).
    """
    if not files_changed:
        raise PatchFileConversionError("files_changed_empty_or_missing")

    items: list[GitPushFileItem] = []

    # Handle list format: [{path, content, change_type}, ...]
    entries = files_changed if isinstance(files_changed, list) else []
    if isinstance(files_changed, dict):
        # dict format: {"path": "foo.py", "content": "...", "change_type": "update"}
        # OR list embedded: {"files": [...]}
        if "files" in files_changed and isinstance(files_changed["files"], list):
            entries = files_changed["files"]
        elif "path" in files_changed and "content" in files_changed:
            entries = [files_changed]
        else:
            raise PatchFileConversionError("files_changed_unrecognized_format")

    if not entries:
        raise PatchFileConversionError("files_changed_empty_or_missing")

    for entry in entries:
        if not isinstance(entry, dict):
            raise PatchFileConversionError("files_changed_invalid_entry")
        path = entry.get("path", "")
        content = entry.get("content")
        change_type = (entry.get("change_type") or "update").lower()

        if change_type == "delete":
            raise PatchFileConversionError(f"delete_operation_not_supported:{path[:80]}")
        if not path:
            raise PatchFileConversionError("empty_file_path")
        if content is None:
            raise PatchFileConversionError(f"no_content_for_path:{path[:80]}")
        if not isinstance(content, str):
            raise PatchFileConversionError(f"binary_content_rejected:{path[:80]}")
        if path.startswith("/"):
            raise PatchFileConversionError(f"absolute_path_forbidden:{path[:80]}")
        if ".." in path or "\\" in path:
            raise PatchFileConversionError(f"path_traversal_forbidden:{path[:80]}")

        items.append(GitPushFileItem(path=path, content=content))

    return items


class PatchProposalService:
    def __init__(self, db: Session, *, provider: GitProvider | None = None) -> None:
        self._db = db
        self._provider = provider
        self._audit = AuditRepository(db)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_directive(self, directive_id: uuid.UUID, project_id: uuid.UUID) -> Directive:
        d = self._db.get(Directive, directive_id)
        if d is None or d.project_id != project_id:
            raise DirectiveMismatchError("directive_not_in_project")
        return d

    def _assert_directive_not_closed(self, d: Directive) -> None:
        if d.status == "CLOSED":
            raise ValueError("directive_closed")

    def _get_patch(self, patch_id: uuid.UUID, directive_id: uuid.UUID) -> PatchProposal:
        p = self._db.get(PatchProposal, patch_id)
        if p is None or p.directive_id != directive_id:
            raise PatchNotFoundError("patch_not_found")
        return p

    def _assert_mutable(self, patch: PatchProposal) -> None:
        if PatchProposalStatus(patch.status) in _IMMUTABLE_STATUSES:
            raise PatchImmutableError(f"patch_immutable_status:{patch.status}")

    # ── Create ────────────────────────────────────────────────────────────────

    def create(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        user_id: uuid.UUID,
        body: PatchProposalCreateRequest,
    ) -> PatchProposalDetail:
        d = self._get_directive(directive_id, project_id)
        self._assert_directive_not_closed(d)

        row = PatchProposal(
            project_id=project_id,
            directive_id=directive_id,
            status=PatchProposalStatus.PROPOSED.value,
            title=body.title,
            summary=body.summary,
            files_changed=body.files_changed,
            unified_diff=body.unified_diff,
            proposed_by_user_id=user_id,
            proposed_by_agent_role=body.proposed_by_agent_role,
        )
        self._db.add(row)
        self._db.flush()

        self._audit.record(
            event_type=AuditEventType.PATCH_PROPOSED,
            event_payload={
                "patch_id": str(row.id),
                "title": body.title,
                "proposed_by_user_id": str(user_id),
                "proposed_by_agent_role": body.proposed_by_agent_role,
                "file_count": len(body.files_changed or {}),
            },
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            workspace_id=d.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )

        return PatchProposalDetail.model_validate(row)

    # ── List / get ────────────────────────────────────────────────────────────

    def list_for_directive(self, project_id: uuid.UUID, directive_id: uuid.UUID) -> PatchProposalListResponse:
        self._get_directive(directive_id, project_id)
        rows = list(self._db.scalars(
            select(PatchProposal)
            .where(PatchProposal.directive_id == directive_id)
            .order_by(PatchProposal.created_at.desc())
        ).all())
        return PatchProposalListResponse(items=[PatchProposalSummary.model_validate(r) for r in rows])

    def get(self, project_id: uuid.UUID, directive_id: uuid.UUID, patch_id: uuid.UUID) -> PatchProposalDetail:
        self._get_directive(directive_id, project_id)
        return PatchProposalDetail.model_validate(self._get_patch(patch_id, directive_id))

    # ── Accept ────────────────────────────────────────────────────────────────

    def accept(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        patch_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PatchProposalAcceptResponse:
        d = self._get_directive(directive_id, project_id)
        patch = self._get_patch(patch_id, directive_id)
        self._assert_mutable(patch)

        existing_accepted = self._db.scalars(
            select(PatchProposal).where(
                PatchProposal.directive_id == directive_id,
                PatchProposal.status == PatchProposalStatus.ACCEPTED.value,
            ).limit(1)
        ).first()
        if existing_accepted is not None:
            raise PatchAlreadyAcceptedError("directive_already_has_accepted_patch")

        now = datetime.now(timezone.utc)
        patch.status = PatchProposalStatus.ACCEPTED.value
        patch.accepted_by_user_id = user_id
        patch.accepted_at = now
        self._db.flush()

        # Proof object
        proof_id: uuid.UUID | None = None
        try:
            proof = ProofObject(
                directive_id=directive_id,
                proof_type=ProofObjectType.GIT_DIFF.value,
                proof_summary=patch.unified_diff[:8192] if patch.unified_diff else f"patch_id={patch.id}",
                proof_uri=None,
                proof_hash=str(patch_id),
                created_by_agent_role="USER",
            )
            self._db.add(proof)
            self._db.flush()
            proof_id = proof.id
        except Exception:
            pass

        self._audit.record(
            event_type=AuditEventType.PATCH_ACCEPTED,
            event_payload={
                "patch_id": str(patch.id),
                "title": patch.title,
                "accepted_by_user_id": str(user_id),
                "proof_object_id": str(proof_id) if proof_id else None,
            },
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            workspace_id=d.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )

        return PatchProposalAcceptResponse(
            id=patch.id,
            status=patch.status,
            accepted_by_user_id=patch.accepted_by_user_id,
            accepted_at=patch.accepted_at,
            proof_object_id=proof_id,
        )

    # ── Reject ────────────────────────────────────────────────────────────────

    def reject(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        patch_id: uuid.UUID,
        user_id: uuid.UUID,
        body: PatchProposalRejectRequest,
    ) -> PatchProposalRejectResponse:
        d = self._get_directive(directive_id, project_id)
        patch = self._get_patch(patch_id, directive_id)
        self._assert_mutable(patch)

        now = datetime.now(timezone.utc)
        patch.status = PatchProposalStatus.REJECTED.value
        patch.rejected_by_user_id = user_id
        patch.rejected_at = now
        patch.rejection_reason = body.reason
        self._db.flush()

        self._audit.record(
            event_type=AuditEventType.PATCH_REJECTED,
            event_payload={
                "patch_id": str(patch.id),
                "title": patch.title,
                "rejected_by_user_id": str(user_id),
                "rejection_reason": body.reason,
            },
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            workspace_id=d.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )

        return PatchProposalRejectResponse(
            id=patch.id,
            status=patch.status,
            rejected_by_user_id=patch.rejected_by_user_id,
            rejected_at=patch.rejected_at,
            rejection_reason=patch.rejection_reason,
        )

    # ── Execute ───────────────────────────────────────────────────────────────

    def execute(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        patch_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PatchExecuteResponse:
        if self._provider is None:
            raise ValueError("git_provider_required_for_execute")

        d = self._get_directive(directive_id, project_id)
        self._assert_directive_not_closed(d)
        patch = self._get_patch(patch_id, directive_id)

        # Guardrail: patch must be ACCEPTED (defensive; service already checks but centralise here)
        from app.services.system_guardrail_service import GuardrailViolationError, SystemGuardrailService
        try:
            SystemGuardrailService(self._db).assert_patch_executable(
                patch=patch,
                directive_id=directive_id,
                project_id=project_id,
                user_id=user_id,
            )
        except GuardrailViolationError as e:
            raise PatchNotExecutableError(e.violation.code) from e

        # Validate status allows execution
        if patch.status != PatchProposalStatus.ACCEPTED.value:
            raise PatchNotExecutableError(f"patch_not_accepted:status={patch.status}")

        # Idempotency: already executed
        if patch.execution_status == PatchExecutionStatus.EXECUTED.value:
            raise PatchAlreadyExecutedError("patch_already_executed")

        # Allow retry only if no commit_sha was recorded
        if (
            patch.execution_status == PatchExecutionStatus.FAILED.value
            and patch.execution_commit_sha is not None
        ):
            raise PatchAlreadyExecutedError("patch_already_executed:commit_recorded")

        # Convert files
        try:
            file_items = _convert_files_changed(patch.files_changed)
        except PatchFileConversionError as e:
            raise PatchFileConversionError(str(e)) from e

        commit_message = (
            f"trident: {patch.title}"
            if patch.title
            else f"trident: apply patch {patch_id} for directive {directive_id}"
        )

        # Mark execution in-flight (no commit SHA yet)
        patch.execution_status = PatchExecutionStatus.FAILED.value  # pessimistic default
        patch.executed_at = datetime.now(timezone.utc)
        patch.executed_by_user_id = user_id
        self._db.flush()

        # Attempt Git push via GitProjectService
        from app.services.git_project_service import (
            GitNotLinkedError,
            GitProjectService,
        )
        git_svc = GitProjectService(self._db, provider=self._provider)
        push_req = GitPushFilesRequest(files=file_items, commit_message=commit_message)

        try:
            result = git_svc.push_files_for_directive(
                project_id,
                directive_id,
                user_id,
                push_req,
            )
        except (GitNotLinkedError, ValueError) as e:
            reason = str(e)
            self._audit.record(
                event_type=AuditEventType.PATCH_EXECUTION_FAILED,
                event_payload={
                    "patch_id": str(patch_id),
                    "directive_id": str(directive_id),
                    "reason_code": reason,
                    "detail_safe": "git_service_error",
                },
                actor_type=AuditActorType.USER,
                actor_id=str(user_id),
                workspace_id=d.workspace_id,
                project_id=project_id,
                directive_id=directive_id,
            )
            self._db.flush()
            raise
        except Exception as e:
            reason = type(e).__name__
            self._audit.record(
                event_type=AuditEventType.PATCH_EXECUTION_FAILED,
                event_payload={
                    "patch_id": str(patch_id),
                    "directive_id": str(directive_id),
                    "reason_code": reason,
                    "detail_safe": "unexpected_error",
                },
                actor_type=AuditActorType.USER,
                actor_id=str(user_id),
                workspace_id=d.workspace_id,
                project_id=project_id,
                directive_id=directive_id,
            )
            self._db.flush()
            raise

        # Success — update patch
        patch.execution_status = PatchExecutionStatus.EXECUTED.value
        patch.execution_commit_sha = result.commit_sha
        patch.execution_branch_name = result.branch_name
        patch.execution_proof_object_id = result.proof_object_id
        self._db.flush()

        self._audit.record(
            event_type=AuditEventType.PATCH_EXECUTED,
            event_payload={
                "patch_id": str(patch_id),
                "directive_id": str(directive_id),
                "commit_sha": result.commit_sha,
                "branch_name": result.branch_name,
                "proof_object_id": str(result.proof_object_id) if result.proof_object_id else None,
                "file_count": result.file_count,
                "executed_by_user_id": str(user_id),
            },
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            workspace_id=d.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )

        return PatchExecuteResponse(
            patch_id=patch_id,
            execution_status=PatchExecutionStatus.EXECUTED.value,
            commit_sha=result.commit_sha,
            branch_name=result.branch_name,
            proof_object_id=result.proof_object_id,
            executed_at=patch.executed_at,
            executed_by_user_id=user_id,
        )
