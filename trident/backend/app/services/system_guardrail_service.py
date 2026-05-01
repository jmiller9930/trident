"""SystemGuardrailService — cross-system invariant checks (TRIDENT_SYSTEM_GUARDRAILS_001).

Read-only diagnostic service.  Never mutates state.
Used both by the /guardrails diagnostic endpoint and as enforcement hooks in service layer.

Severity:
  INFO     — informational, no action required
  WARNING  — degraded / unexpected but not blocking
  ERROR    — integrity issue; should be investigated
  BLOCKING — action must fail; service raises before committing
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType, DirectiveStatus
from app.models.git_branch_log import GitBranchLog
from app.models.patch_proposal import PatchExecutionStatus, PatchProposal, PatchProposalStatus
from app.models.proof_object import ProofObject
from app.models.validation_run import ValidationRun, ValidationStatus
from app.repositories.audit_repository import AuditRepository


# ── Violation model ───────────────────────────────────────────────────────────

@dataclass
class Violation:
    code: str
    severity: str           # INFO | WARNING | ERROR | BLOCKING
    message: str
    related_table: str
    related_id: str | None = None
    suggested_action: str | None = None

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "related_table": self.related_table,
            "related_id": self.related_id,
            "suggested_action": self.suggested_action,
        }


@dataclass
class GuardrailResult:
    directive_id: uuid.UUID
    project_id: uuid.UUID
    checked_at: datetime
    violations: list[Violation] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "FAIL" if self.violations else "PASS"

    @property
    def blocking_violations(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == "BLOCKING"]

    def has_blocking(self) -> bool:
        return bool(self.blocking_violations)


class GuardrailViolationError(Exception):
    """Raised by enforcement hooks when a BLOCKING violation is found."""

    def __init__(self, violation: Violation) -> None:
        super().__init__(violation.message)
        self.violation = violation


# ── Service ───────────────────────────────────────────────────────────────────

class SystemGuardrailService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._audit = AuditRepository(db)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _audit_exists(self, directive_id: uuid.UUID, event_type: AuditEventType) -> bool:
        return self._db.scalars(
            select(AuditEvent).where(
                AuditEvent.directive_id == directive_id,
                AuditEvent.event_type == event_type.value,
            ).limit(1)
        ).first() is not None

    def _audit_exists_with_payload_key(
        self, directive_id: uuid.UUID, event_type: AuditEventType, key: str, value: str
    ) -> bool:
        rows = list(self._db.scalars(
            select(AuditEvent).where(
                AuditEvent.directive_id == directive_id,
                AuditEvent.event_type == event_type.value,
            )
        ).all())
        return any(str(r.event_payload_json.get(key, "")) == value for r in rows)

    # ── Check A: Closed directive integrity ───────────────────────────────────

    def _check_closed_integrity(
        self, directive: Directive, violations: list[Violation]
    ) -> None:
        if directive.status != DirectiveStatus.CLOSED.value:
            return

        if not self._audit_exists(directive.id, AuditEventType.SIGNOFF_COMPLETED):
            violations.append(Violation(
                code="CLOSED_MISSING_SIGNOFF_AUDIT",
                severity="ERROR",
                message="CLOSED directive has no SIGNOFF_COMPLETED audit event.",
                related_table="audit_events",
                related_id=str(directive.id),
                suggested_action="Investigate signoff service — audit may have failed silently.",
            ))

        proof = self._db.scalars(
            select(ProofObject).where(
                ProofObject.directive_id == directive.id,
                ProofObject.proof_type == "DIRECTIVE_SIGNOFF",
            ).limit(1)
        ).first()
        if proof is None:
            violations.append(Violation(
                code="CLOSED_MISSING_SIGNOFF_PROOF",
                severity="WARNING",
                message="CLOSED directive has no DIRECTIVE_SIGNOFF proof object.",
                related_table="proof_objects",
                related_id=str(directive.id),
                suggested_action="Proof creation is non-blocking; this is expected if proof creation failed.",
            ))

        passed = self._db.scalars(
            select(ValidationRun).where(
                ValidationRun.directive_id == directive.id,
                ValidationRun.status == ValidationStatus.PASSED.value,
            ).limit(1)
        ).first()
        if passed is None:
            violations.append(Violation(
                code="CLOSED_WITHOUT_PASSED_VALIDATION",
                severity="ERROR",
                message="CLOSED directive has no PASSED validation run.",
                related_table="validation_runs",
                related_id=str(directive.id),
                suggested_action="Investigate SignoffService — eligibility check may have been bypassed.",
            ))

    # ── Check B: Patch execution integrity ────────────────────────────────────

    def _check_patch_execution_integrity(
        self, directive_id: uuid.UUID, violations: list[Violation]
    ) -> None:
        executed = list(self._db.scalars(
            select(PatchProposal).where(
                PatchProposal.directive_id == directive_id,
                PatchProposal.execution_status == PatchExecutionStatus.EXECUTED.value,
            )
        ).all())

        for p in executed:
            if not p.execution_commit_sha:
                violations.append(Violation(
                    code="EXECUTED_PATCH_MISSING_COMMIT_SHA",
                    severity="ERROR",
                    message=f"Patch {p.id} is EXECUTED but has no execution_commit_sha.",
                    related_table="patch_proposals",
                    related_id=str(p.id),
                    suggested_action="Check patch execution service for partial writes.",
                ))
            if not p.execution_branch_name:
                violations.append(Violation(
                    code="EXECUTED_PATCH_MISSING_BRANCH_NAME",
                    severity="WARNING",
                    message=f"Patch {p.id} is EXECUTED but has no execution_branch_name.",
                    related_table="patch_proposals",
                    related_id=str(p.id),
                ))
            if p.execution_commit_sha:
                branch_log = self._db.scalars(
                    select(GitBranchLog).where(
                        GitBranchLog.directive_id == directive_id,
                        GitBranchLog.event_type == "commit_pushed",
                        GitBranchLog.commit_sha == p.execution_commit_sha,
                    ).limit(1)
                ).first()
                if branch_log is None:
                    violations.append(Violation(
                        code="EXECUTED_PATCH_MISSING_BRANCH_LOG",
                        severity="ERROR",
                        message=f"Patch {p.id} executed (SHA={p.execution_commit_sha[:8]}) but no matching git_branch_log commit_pushed.",
                        related_table="git_branch_log",
                        related_id=str(directive_id),
                        suggested_action="Git branch log may not have been written by push_files_for_directive.",
                    ))

    # ── Check C: Validation / signoff integrity (non-closed directives) ───────

    def _check_validation_audit_completeness(
        self, directive_id: uuid.UUID, violations: list[Violation]
    ) -> None:
        runs = list(self._db.scalars(
            select(ValidationRun).where(ValidationRun.directive_id == directive_id)
        ).all())

        for r in runs:
            if r.status == ValidationStatus.PASSED.value:
                if not self._audit_exists_with_payload_key(
                    directive_id, AuditEventType.VALIDATION_PASSED, "validation_id", str(r.id)
                ):
                    violations.append(Violation(
                        code="VALIDATION_PASSED_MISSING_AUDIT",
                        severity="WARNING",
                        message=f"ValidationRun {r.id} is PASSED but has no VALIDATION_PASSED audit event.",
                        related_table="validation_runs",
                        related_id=str(r.id),
                        suggested_action="Check ValidationRunService.complete for audit emission.",
                    ))
            elif r.status == ValidationStatus.FAILED.value:
                if not self._audit_exists_with_payload_key(
                    directive_id, AuditEventType.VALIDATION_FAILED, "validation_id", str(r.id)
                ):
                    violations.append(Violation(
                        code="VALIDATION_FAILED_MISSING_AUDIT",
                        severity="WARNING",
                        message=f"ValidationRun {r.id} is FAILED but has no VALIDATION_FAILED audit event.",
                        related_table="validation_runs",
                        related_id=str(r.id),
                    ))

    # ── Check D: Git linkage integrity ────────────────────────────────────────

    def _check_git_linkage(
        self, directive_id: uuid.UUID, violations: list[Violation]
    ) -> None:
        commit_rows = list(self._db.scalars(
            select(GitBranchLog).where(
                GitBranchLog.directive_id == directive_id,
                GitBranchLog.event_type == "commit_pushed",
            )
        ).all())

        if not commit_rows:
            return

        branch_row = self._db.scalars(
            select(GitBranchLog).where(
                GitBranchLog.directive_id == directive_id,
                GitBranchLog.event_type == "branch_created",
            ).order_by(GitBranchLog.created_at.asc()).limit(1)
        ).first()

        if branch_row is None:
            for cr in commit_rows:
                violations.append(Violation(
                    code="COMMIT_WITHOUT_BRANCH_CREATED",
                    severity="ERROR",
                    message=f"git_branch_log has commit_pushed for directive {directive_id} but no branch_created.",
                    related_table="git_branch_log",
                    related_id=str(cr.id),
                    suggested_action="Verify that create_branch_for_directive ran before push_files_for_directive.",
                ))
        else:
            for cr in commit_rows:
                if cr.created_at and branch_row.created_at:
                    def _as_utc(dt: datetime) -> datetime:
                        if dt.tzinfo is None:
                            return dt.replace(tzinfo=timezone.utc)
                        return dt

                    if _as_utc(cr.created_at) < _as_utc(branch_row.created_at):
                        violations.append(Violation(
                            code="COMMIT_BEFORE_BRANCH_CREATED",
                            severity="WARNING",
                            message="commit_pushed timestamp precedes branch_created timestamp.",
                            related_table="git_branch_log",
                            related_id=str(cr.id),
                        ))

    # ── Check E: Audit completeness for patches ────────────────────────────────

    def _check_patch_audit_completeness(
        self, directive_id: uuid.UUID, violations: list[Violation]
    ) -> None:
        patches = list(self._db.scalars(
            select(PatchProposal).where(PatchProposal.directive_id == directive_id)
        ).all())

        for p in patches:
            if p.status == PatchProposalStatus.ACCEPTED.value:
                if not self._audit_exists_with_payload_key(
                    directive_id, AuditEventType.PATCH_ACCEPTED, "patch_id", str(p.id)
                ):
                    violations.append(Violation(
                        code="ACCEPTED_PATCH_MISSING_AUDIT",
                        severity="WARNING",
                        message=f"Patch {p.id} is ACCEPTED but has no PATCH_ACCEPTED audit event.",
                        related_table="patch_proposals",
                        related_id=str(p.id),
                        suggested_action="Check PatchProposalService.accept for audit emission.",
                    ))
            if p.execution_status == PatchExecutionStatus.EXECUTED.value:
                if not self._audit_exists_with_payload_key(
                    directive_id, AuditEventType.PATCH_EXECUTED, "patch_id", str(p.id)
                ):
                    violations.append(Violation(
                        code="EXECUTED_PATCH_MISSING_AUDIT",
                        severity="WARNING",
                        message=f"Patch {p.id} is EXECUTED but has no PATCH_EXECUTED audit event.",
                        related_table="patch_proposals",
                        related_id=str(p.id),
                    ))

    # ── Full diagnostic check ─────────────────────────────────────────────────

    def check_directive(
        self, directive_id: uuid.UUID, project_id: uuid.UUID
    ) -> GuardrailResult:
        result = GuardrailResult(
            directive_id=directive_id,
            project_id=project_id,
            checked_at=datetime.now(timezone.utc),
        )
        directive = self._db.get(Directive, directive_id)
        if directive is None or directive.project_id != project_id:
            result.violations.append(Violation(
                code="DIRECTIVE_NOT_FOUND",
                severity="BLOCKING",
                message="Directive not found or does not belong to this project.",
                related_table="directives",
                related_id=str(directive_id),
            ))
            return result

        v = result.violations
        self._check_closed_integrity(directive, v)
        self._check_patch_execution_integrity(directive_id, v)
        self._check_validation_audit_completeness(directive_id, v)
        self._check_git_linkage(directive_id, v)
        self._check_patch_audit_completeness(directive_id, v)
        return result

    # ── Enforcement hooks (called by service layer) ────────────────────────────

    def assert_patch_executable(
        self,
        *,
        patch: PatchProposal,
        directive_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Raise GuardrailViolationError if the patch cannot be executed safely."""
        if patch.status != PatchProposalStatus.ACCEPTED.value:
            v = Violation(
                code="PATCH_NOT_ACCEPTED",
                severity="BLOCKING",
                message=f"Patch {patch.id} must be ACCEPTED before execution (status={patch.status}).",
                related_table="patch_proposals",
                related_id=str(patch.id),
                suggested_action="Accept the patch via POST /patches/{patch_id}/accept first.",
            )
            self._emit_guardrail_audit(v, project_id=project_id, directive_id=directive_id, user_id=user_id)
            raise GuardrailViolationError(v)

    def assert_signoff_preconditions(
        self,
        *,
        directive: Directive,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Validate signoff preconditions beyond the basic eligibility check."""
        if self._audit_exists(directive.id, AuditEventType.SIGNOFF_COMPLETED):
            v = Violation(
                code="SIGNOFF_ALREADY_RECORDED",
                severity="BLOCKING",
                message="A SIGNOFF_COMPLETED audit already exists for this directive.",
                related_table="audit_events",
                related_id=str(directive.id),
                suggested_action="Directive may already be closed. Check directive.status.",
            )
            self._emit_guardrail_audit(v, project_id=project_id, directive_id=directive.id, user_id=user_id)
            raise GuardrailViolationError(v)

    # ── Audit helper ──────────────────────────────────────────────────────────

    def _emit_guardrail_audit(
        self,
        violation: Violation,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        try:
            self._audit.record(
                event_type=AuditEventType.CONTROL_PLANE_ACTION,
                event_payload={
                    "action": "guardrail_block",
                    "violation_code": violation.code,
                    "severity": violation.severity,
                    "message": violation.message,
                    "related_table": violation.related_table,
                    "blocked": True,
                },
                actor_type=AuditActorType.SYSTEM,
                actor_id=str(user_id),
                project_id=project_id,
                directive_id=directive_id,
            )
        except Exception:
            pass  # audit failure is non-blocking for the block itself
