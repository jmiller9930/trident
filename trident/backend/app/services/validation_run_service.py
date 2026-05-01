"""ValidationRunService — post-commit validation lifecycle (VALIDATION_001).

Lifecycle: PENDING → RUNNING → PASSED | FAILED | WAIVED
Terminal statuses (PASSED, FAILED, WAIVED) are immutable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType, ProofObjectType
from app.models.patch_proposal import PatchProposal
from app.models.proof_object import ProofObject
from app.models.validation_run import ValidationRun, ValidationRunType, ValidationStatus, _TERMINAL_STATUSES
from app.repositories.audit_repository import AuditRepository
from app.schemas.validation_schemas import (
    ValidationRunCompleteRequest,
    ValidationRunCreateRequest,
    ValidationRunDetail,
    ValidationRunListResponse,
    ValidationRunSummary,
    ValidationRunWaiveRequest,
)


class ValidationTerminalError(ValueError):
    pass


class ValidationNotFoundError(ValueError):
    pass


class ValidationDirectiveMismatchError(ValueError):
    pass


class ValidationPatchMismatchError(ValueError):
    pass


class ValidationInvalidTransitionError(ValueError):
    pass


class ValidationRunService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._audit = AuditRepository(db)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_directive(self, directive_id: uuid.UUID, project_id: uuid.UUID) -> Directive:
        d = self._db.get(Directive, directive_id)
        if d is None or d.project_id != project_id:
            raise ValidationDirectiveMismatchError("directive_not_in_project")
        return d

    def _assert_directive_not_closed(self, d: Directive) -> None:
        if d.status == "CLOSED":
            raise ValidationTerminalError("directive_closed")

    def _get_run(self, validation_id: uuid.UUID, directive_id: uuid.UUID) -> ValidationRun:
        v = self._db.get(ValidationRun, validation_id)
        if v is None or v.directive_id != directive_id:
            raise ValidationNotFoundError("validation_not_found")
        return v

    def _assert_not_terminal(self, run: ValidationRun) -> None:
        if ValidationStatus(run.status) in _TERMINAL_STATUSES:
            raise ValidationTerminalError(f"validation_run_immutable:status={run.status}")

    def _emit_audit(
        self,
        event_type: AuditEventType,
        *,
        run: ValidationRun,
        directive: Directive,
        user_id: uuid.UUID,
        extra: dict | None = None,
    ) -> None:
        payload = {
            "validation_id": str(run.id),
            "directive_id": str(run.directive_id),
            "project_id": str(run.project_id),
            "patch_id": str(run.patch_id) if run.patch_id else None,
            "commit_sha": run.commit_sha,
            "validation_type": run.validation_type,
            "status": run.status,
            **(extra or {}),
        }
        self._audit.record(
            event_type=event_type,
            event_payload=payload,
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            workspace_id=directive.workspace_id,
            project_id=run.project_id,
            directive_id=run.directive_id,
        )

    def _try_create_proof(self, run: ValidationRun, directive: Directive) -> uuid.UUID | None:
        if run.status not in (ValidationStatus.PASSED.value, ValidationStatus.FAILED.value):
            return None
        proof_type = (
            ProofObjectType.VALIDATION_RUN_PASSED.value
            if run.status == ValidationStatus.PASSED.value
            else ProofObjectType.VALIDATION_RUN_FAILED.value
        )
        try:
            proof = ProofObject(
                directive_id=run.directive_id,
                proof_type=proof_type,
                proof_summary=run.result_summary,
                proof_uri=None,
                proof_hash=run.commit_sha or str(run.id),
                created_by_agent_role="USER",
            )
            self._db.add(proof)
            self._db.flush()
            return proof.id
        except Exception:
            return None

    # ── Create ────────────────────────────────────────────────────────────────

    def create(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        user_id: uuid.UUID,
        body: ValidationRunCreateRequest,
    ) -> ValidationRunDetail:
        d = self._get_directive(directive_id, project_id)
        self._assert_directive_not_closed(d)

        if body.patch_id is not None:
            patch = self._db.get(PatchProposal, body.patch_id)
            if patch is None or patch.directive_id != directive_id:
                raise ValidationPatchMismatchError("patch_not_in_directive")
            if body.commit_sha and patch.execution_commit_sha and body.commit_sha != patch.execution_commit_sha:
                raise ValidationPatchMismatchError(
                    f"commit_sha_mismatch:expected={patch.execution_commit_sha[:12]} got={body.commit_sha[:12]}"
                )

        run = ValidationRun(
            project_id=project_id,
            directive_id=directive_id,
            patch_id=body.patch_id,
            commit_sha=body.commit_sha,
            status=ValidationStatus.PENDING.value,
            validation_type=body.validation_type.value,
            result_summary=body.result_summary,
            result_payload_json=body.result_payload_json,
            started_by_user_id=user_id,
        )
        self._db.add(run)
        self._db.flush()

        self._emit_audit(AuditEventType.VALIDATION_CREATED, run=run, directive=d, user_id=user_id)

        return ValidationRunDetail.model_validate(run)

    # ── List / get ────────────────────────────────────────────────────────────

    def list_for_directive(self, project_id: uuid.UUID, directive_id: uuid.UUID) -> ValidationRunListResponse:
        self._get_directive(directive_id, project_id)
        rows = list(self._db.scalars(
            select(ValidationRun)
            .where(ValidationRun.directive_id == directive_id)
            .order_by(ValidationRun.created_at.desc())
        ).all())
        return ValidationRunListResponse(items=[ValidationRunSummary.model_validate(r) for r in rows])

    def get(
        self, project_id: uuid.UUID, directive_id: uuid.UUID, validation_id: uuid.UUID
    ) -> ValidationRunDetail:
        self._get_directive(directive_id, project_id)
        return ValidationRunDetail.model_validate(self._get_run(validation_id, directive_id))

    # ── Start ─────────────────────────────────────────────────────────────────

    def start(
        self, project_id: uuid.UUID, directive_id: uuid.UUID, validation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ValidationRunDetail:
        d = self._get_directive(directive_id, project_id)
        self._assert_directive_not_closed(d)
        run = self._get_run(validation_id, directive_id)
        self._assert_not_terminal(run)
        if run.status != ValidationStatus.PENDING.value:
            raise ValidationInvalidTransitionError(f"cannot_start_from:{run.status}")
        run.status = ValidationStatus.RUNNING.value
        self._db.flush()
        self._emit_audit(AuditEventType.VALIDATION_STARTED, run=run, directive=d, user_id=user_id)
        return ValidationRunDetail.model_validate(run)

    # ── Complete ──────────────────────────────────────────────────────────────

    def complete(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        validation_id: uuid.UUID,
        user_id: uuid.UUID,
        body: ValidationRunCompleteRequest,
    ) -> ValidationRunDetail:
        d = self._get_directive(directive_id, project_id)
        self._assert_directive_not_closed(d)
        run = self._get_run(validation_id, directive_id)
        self._assert_not_terminal(run)
        if run.status not in (ValidationStatus.PENDING.value, ValidationStatus.RUNNING.value):
            raise ValidationInvalidTransitionError(f"cannot_complete_from:{run.status}")

        now = datetime.now(timezone.utc)
        new_status = ValidationStatus.PASSED if body.passed else ValidationStatus.FAILED
        run.status = new_status.value
        run.result_summary = body.result_summary
        run.result_payload_json = body.result_payload_json
        run.completed_by_user_id = user_id
        run.completed_at = now
        self._db.flush()

        proof_id = self._try_create_proof(run, d)

        audit_event = AuditEventType.VALIDATION_PASSED if body.passed else AuditEventType.VALIDATION_FAILED
        self._emit_audit(
            audit_event,
            run=run,
            directive=d,
            user_id=user_id,
            extra={"proof_object_id": str(proof_id) if proof_id else None},
        )

        result = ValidationRunDetail.model_validate(run)
        result = result.model_copy(update={"proof_object_id": proof_id})
        return result

    # ── Waive ─────────────────────────────────────────────────────────────────

    def waive(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        validation_id: uuid.UUID,
        user_id: uuid.UUID,
        body: ValidationRunWaiveRequest,
    ) -> ValidationRunDetail:
        d = self._get_directive(directive_id, project_id)
        self._assert_directive_not_closed(d)
        run = self._get_run(validation_id, directive_id)
        self._assert_not_terminal(run)

        now = datetime.now(timezone.utc)
        run.status = ValidationStatus.WAIVED.value
        run.result_summary = body.reason
        run.completed_by_user_id = user_id
        run.completed_at = now
        self._db.flush()

        self._emit_audit(
            AuditEventType.VALIDATION_WAIVED,
            run=run,
            directive=d,
            user_id=user_id,
            extra={"waive_reason": body.reason},
        )

        return ValidationRunDetail.model_validate(run)
