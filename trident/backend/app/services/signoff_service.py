"""SignoffService — directive sign-off and governed closure (SIGNOFF_001).

Eligibility rules:
  1. At least one validation_run.status == PASSED.
  2. No validation_run.status == FAILED (unless that run is absent — WAIVED is acceptable).
  3. Directive.status must be ISSUED.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType, DirectiveStatus, ProofObjectType
from app.models.proof_object import ProofObject
from app.models.validation_run import ValidationRun, ValidationStatus
from app.repositories.audit_repository import AuditRepository


class SignoffNotEligibleError(ValueError):
    pass


class DirectiveNotIssuedError(ValueError):
    pass


class DirectiveAlreadyClosedError(ValueError):
    pass


class DirectiveMismatchError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationSummary:
    total: int
    passed: int
    failed: int
    waived: int

    @property
    def has_passed(self) -> bool:
        return self.passed > 0

    @property
    def has_unwaived_failure(self) -> bool:
        return self.failed > 0

    def eligibility_reason(self) -> str | None:
        if self.total == 0:
            return "no_validation_runs"
        if not self.has_passed:
            return "no_passed_validations"
        if self.has_unwaived_failure:
            return f"unwaived_failure_count={self.failed}"
        return None


class SignoffService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._audit = AuditRepository(db)

    def _get_directive(self, directive_id: uuid.UUID, project_id: uuid.UUID) -> Directive:
        d = self._db.get(Directive, directive_id)
        if d is None or d.project_id != project_id:
            raise DirectiveMismatchError("directive_not_in_project")
        return d

    def _validation_summary(self, directive_id: uuid.UUID) -> ValidationSummary:
        runs = list(self._db.scalars(
            select(ValidationRun).where(ValidationRun.directive_id == directive_id)
        ).all())
        passed = sum(1 for r in runs if r.status == ValidationStatus.PASSED.value)
        failed = sum(1 for r in runs if r.status == ValidationStatus.FAILED.value)
        waived = sum(1 for r in runs if r.status == ValidationStatus.WAIVED.value)
        return ValidationSummary(total=len(runs), passed=passed, failed=failed, waived=waived)

    def signoff(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Directive:
        d = self._get_directive(directive_id, project_id)

        if d.status == DirectiveStatus.CLOSED.value:
            raise DirectiveAlreadyClosedError("directive_already_closed")
        if d.status != DirectiveStatus.ISSUED.value:
            raise DirectiveNotIssuedError(f"directive_not_issued:status={d.status}")

        summary = self._validation_summary(directive_id)
        reason = summary.eligibility_reason()
        if reason is not None:
            raise SignoffNotEligibleError(reason)

        # Guardrail: detect duplicate signoff (SIGNOFF_COMPLETED audit already exists)
        from app.services.system_guardrail_service import GuardrailViolationError, SystemGuardrailService
        try:
            SystemGuardrailService(self._db).assert_signoff_preconditions(
                directive=d,
                project_id=project_id,
                user_id=user_id,
            )
        except GuardrailViolationError as e:
            raise DirectiveAlreadyClosedError(e.violation.code) from e

        now = datetime.now(timezone.utc)
        d.status = DirectiveStatus.CLOSED.value
        d.closed_at = now
        d.closed_by_user_id = user_id
        self._db.flush()

        # Proof — non-blocking
        proof_id: uuid.UUID | None = None
        try:
            proof = ProofObject(
                directive_id=directive_id,
                proof_type=ProofObjectType.DIRECTIVE_SIGNOFF.value,
                proof_summary=(
                    f"Directive closed with {summary.passed} passed, "
                    f"{summary.waived} waived, {summary.failed} failed"
                ),
                proof_hash=str(directive_id),
                proof_uri=None,
                created_by_agent_role="USER",
            )
            self._db.add(proof)
            self._db.flush()
            proof_id = proof.id
        except Exception:
            pass

        self._audit.record(
            event_type=AuditEventType.SIGNOFF_COMPLETED,
            event_payload={
                "directive_id": str(directive_id),
                "project_id": str(project_id),
                "closed_by_user_id": str(user_id),
                "closed_at": now.isoformat(),
                "proof_object_id": str(proof_id) if proof_id else None,
                "validation_summary": {
                    "total_runs": summary.total,
                    "passed_count": summary.passed,
                    "failed_count": summary.failed,
                    "waived_count": summary.waived,
                },
            },
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            workspace_id=d.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )

        return d, proof_id
