"""DecisionEngineService — deterministic patch-level decision synthesis (TRIDENT_DECISION_ENGINE_001).

Read-only by default.  No mutations except DecisionRecord persistence when explicitly requested.
Decision rules are deterministic from DB state — no model calls, no LLM.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_record import DecisionRecommendation, DecisionRecord
from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType, DirectiveStatus
from app.models.patch_proposal import PatchExecutionStatus, PatchProposal, PatchProposalStatus
from app.models.patch_review import PatchReview, ReviewerRecommendation
from app.models.validation_run import ValidationRun, ValidationStatus
from app.repositories.audit_repository import AuditRepository

# Confidence threshold: reviewer ACCEPT above this → recommend ACCEPT_PATCH
REVIEWER_ACCEPT_CONFIDENCE_THRESHOLD = 0.75


# ── Decision output ───────────────────────────────────────────────────────────

@dataclass
class EvidenceItem:
    source: str          # e.g. "patch_review", "validation_run", "patch_proposal"
    detail: str
    source_id: str | None = None


@dataclass
class DecisionOutput:
    recommendation: str
    confidence: float
    summary: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    recommended_next_api_action: str | None = None
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def as_dict(self) -> dict[str, Any]:
        return {
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "summary": self.summary,
            "evidence": [
                {"source": e.source, "detail": e.detail, "source_id": e.source_id}
                for e in self.evidence
            ],
            "blocking_reasons": self.blocking_reasons,
            "recommended_next_api_action": self.recommended_next_api_action,
            "computed_at": self.computed_at.isoformat(),
        }


class DecisionNotFoundError(ValueError):
    pass


# ── Rule engine ───────────────────────────────────────────────────────────────

class DecisionEngineService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._audit = AuditRepository(db)

    # ── Data loaders ─────────────────────────────────────────────────────────

    def _get_directive(self, directive_id: uuid.UUID, project_id: uuid.UUID) -> Directive:
        d = self._db.get(Directive, directive_id)
        if d is None or d.project_id != project_id:
            raise DecisionNotFoundError("directive_not_in_project")
        return d

    def _get_patch(self, patch_id: uuid.UUID, directive_id: uuid.UUID) -> PatchProposal | None:
        p = self._db.get(PatchProposal, patch_id)
        if p is None or p.directive_id != directive_id:
            return None
        return p

    def _latest_patch(self, directive_id: uuid.UUID) -> PatchProposal | None:
        return self._db.scalars(
            select(PatchProposal)
            .where(PatchProposal.directive_id == directive_id)
            .order_by(PatchProposal.created_at.desc())
            .limit(1)
        ).first()

    def _latest_accepted_patch(self, directive_id: uuid.UUID) -> PatchProposal | None:
        return self._db.scalars(
            select(PatchProposal)
            .where(
                PatchProposal.directive_id == directive_id,
                PatchProposal.status == PatchProposalStatus.ACCEPTED.value,
            )
            .order_by(PatchProposal.created_at.desc())
            .limit(1)
        ).first()

    def _reviews_for_patch(self, patch_id: uuid.UUID) -> list[PatchReview]:
        return list(self._db.scalars(
            select(PatchReview)
            .where(PatchReview.patch_id == patch_id)
            .order_by(PatchReview.created_at.desc())
        ).all())

    def _validations_for_directive(self, directive_id: uuid.UUID) -> list[ValidationRun]:
        return list(self._db.scalars(
            select(ValidationRun)
            .where(ValidationRun.directive_id == directive_id)
            .order_by(ValidationRun.created_at.desc())
        ).all())

    # ── Rule: patch-level decision ────────────────────────────────────────────

    def _decide_for_patch(
        self,
        directive: Directive,
        patch: PatchProposal,
        reviews: list[PatchReview],
        validations: list[ValidationRun],
    ) -> DecisionOutput:
        evidence: list[EvidenceItem] = []
        blocking: list[str] = []

        # ── Rule 1: CLOSED directive ─────────────────────────────────────────
        if directive.status == DirectiveStatus.CLOSED.value:
            return DecisionOutput(
                recommendation=DecisionRecommendation.NO_ACTION.value,
                confidence=1.0,
                summary="Directive is closed. No further action required.",
                evidence=[EvidenceItem("directive", f"status={directive.status}")],
            )

        # ── Rule 2: REJECTED patch ───────────────────────────────────────────
        if patch.status == PatchProposalStatus.REJECTED.value:
            evidence.append(EvidenceItem("patch_proposal", "Patch was rejected.", str(patch.id)))
            return DecisionOutput(
                recommendation=DecisionRecommendation.NO_ACTION.value,
                confidence=1.0,
                summary="Patch was rejected. A new patch proposal is required.",
                evidence=evidence,
                recommended_next_api_action="POST /patches/ to create a new proposal",
            )

        # ── Rule 3: ACCEPTED patch + not executed ────────────────────────────
        if (
            patch.status == PatchProposalStatus.ACCEPTED.value
            and patch.execution_status != PatchExecutionStatus.EXECUTED.value
        ):
            evidence.append(EvidenceItem("patch_proposal", f"Patch ACCEPTED, execution_status={patch.execution_status}", str(patch.id)))
            return DecisionOutput(
                recommendation=DecisionRecommendation.EXECUTE_PATCH.value,
                confidence=0.95,
                summary="Patch is accepted and ready for execution.",
                evidence=evidence,
                recommended_next_api_action=f"POST /patches/{patch.id}/execute",
            )

        # ── Rule 4: Patch executed — check validation ────────────────────────
        if (
            patch.status == PatchProposalStatus.ACCEPTED.value
            and patch.execution_status == PatchExecutionStatus.EXECUTED.value
        ):
            evidence.append(EvidenceItem("patch_proposal",
                f"Patch executed (SHA={patch.execution_commit_sha or '?'})", str(patch.id)))

            if not validations:
                return DecisionOutput(
                    recommendation=DecisionRecommendation.CREATE_VALIDATION.value,
                    confidence=0.90,
                    summary="Patch executed successfully. Create a validation run to verify the result.",
                    evidence=evidence,
                    recommended_next_api_action="POST /validations/ to create a validation run",
                )

            passed = [v for v in validations if v.status == ValidationStatus.PASSED.value]
            failed = [v for v in validations if v.status == ValidationStatus.FAILED.value]
            waived = [v for v in validations if v.status == ValidationStatus.WAIVED.value]

            for v in passed:
                evidence.append(EvidenceItem("validation_run", f"PASSED: {v.validation_type}", str(v.id)))
            for v in failed:
                evidence.append(EvidenceItem("validation_run", f"FAILED: {v.validation_type}", str(v.id)))
            for v in waived:
                evidence.append(EvidenceItem("validation_run", f"WAIVED: {v.validation_type}", str(v.id)))

            if failed:
                return DecisionOutput(
                    recommendation=DecisionRecommendation.REQUEST_CHANGES.value,
                    confidence=0.90,
                    summary=f"{len(failed)} validation run(s) FAILED. Waive or fix before signoff.",
                    evidence=evidence,
                    blocking_reasons=[f"validation_failed:{v.id}" for v in failed],
                    recommended_next_api_action="POST /validations/{id}/waive or fix and re-run",
                )

            if passed:
                return DecisionOutput(
                    recommendation=DecisionRecommendation.SIGNOFF.value,
                    confidence=0.90,
                    summary="Validations passed. Directive is eligible for sign-off.",
                    evidence=evidence,
                    recommended_next_api_action="POST /directives/{id}/signoff",
                )

            # Only pending/running validations
            return DecisionOutput(
                recommendation=DecisionRecommendation.BLOCKED.value,
                confidence=0.80,
                summary="Validation runs exist but none are PASSED yet.",
                evidence=evidence,
                blocking_reasons=["validation_not_complete"],
                recommended_next_api_action="POST /validations/{id}/complete",
            )

        # ── Rule 5: PROPOSED patch — evaluate reviews ─────────────────────────
        if patch.status == PatchProposalStatus.PROPOSED.value:
            if not reviews:
                evidence.append(EvidenceItem("patch_proposal", "No reviews exist for this patch.", str(patch.id)))
                return DecisionOutput(
                    recommendation=DecisionRecommendation.BLOCKED.value,
                    confidence=0.95,
                    summary="No reviewer recommendation exists. Run the Reviewer agent first.",
                    evidence=evidence,
                    blocking_reasons=["reviewer_required"],
                    recommended_next_api_action=f"POST /patches/{patch.id}/agents/reviewer/run",
                )

            latest = reviews[0]
            evidence.append(EvidenceItem(
                "patch_review",
                f"Latest review: {latest.recommendation} (confidence={latest.confidence:.2f})",
                str(latest.id),
            ))

            if latest.recommendation == ReviewerRecommendation.REJECT.value:
                return DecisionOutput(
                    recommendation=DecisionRecommendation.REJECT_PATCH.value,
                    confidence=latest.confidence,
                    summary=f"Reviewer recommends REJECT: {latest.summary or 'no summary'}",
                    evidence=evidence,
                    recommended_next_api_action=f"POST /patches/{patch.id}/reject",
                )

            if latest.recommendation == ReviewerRecommendation.NEEDS_CHANGES.value:
                return DecisionOutput(
                    recommendation=DecisionRecommendation.REQUEST_CHANGES.value,
                    confidence=latest.confidence,
                    summary=f"Reviewer recommends NEEDS_CHANGES: {latest.summary or 'no summary'}",
                    evidence=evidence,
                    blocking_reasons=["reviewer_requested_changes"],
                    recommended_next_api_action=f"POST /patches/{patch.id}/reject with reason",
                )

            if latest.recommendation == ReviewerRecommendation.ACCEPT.value:
                if latest.confidence >= REVIEWER_ACCEPT_CONFIDENCE_THRESHOLD:
                    return DecisionOutput(
                        recommendation=DecisionRecommendation.ACCEPT_PATCH.value,
                        confidence=latest.confidence,
                        summary=f"Reviewer recommends ACCEPT with confidence {latest.confidence:.2f}.",
                        evidence=evidence,
                        recommended_next_api_action=f"POST /patches/{patch.id}/accept",
                    )
                else:
                    blocking.append(f"reviewer_confidence_below_threshold:{latest.confidence:.2f}<{REVIEWER_ACCEPT_CONFIDENCE_THRESHOLD}")
                    evidence.append(EvidenceItem(
                        "threshold", f"Confidence {latest.confidence:.2f} below threshold {REVIEWER_ACCEPT_CONFIDENCE_THRESHOLD}"
                    ))
                    return DecisionOutput(
                        recommendation=DecisionRecommendation.BLOCKED.value,
                        confidence=latest.confidence,
                        summary=f"Reviewer ACCEPT confidence ({latest.confidence:.2f}) below threshold ({REVIEWER_ACCEPT_CONFIDENCE_THRESHOLD}). Human review required.",
                        evidence=evidence,
                        blocking_reasons=blocking,
                        recommended_next_api_action="Run reviewer again or manually review and accept/reject",
                    )

        # ── Fallback ─────────────────────────────────────────────────────────
        return DecisionOutput(
            recommendation=DecisionRecommendation.NO_ACTION.value,
            confidence=0.5,
            summary="No clear next action determined from current state.",
            evidence=evidence,
        )

    # ── Public compute (no persistence) ──────────────────────────────────────

    def compute(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        patch_id: uuid.UUID | None = None,
    ) -> DecisionOutput:
        directive = self._get_directive(directive_id, project_id)

        if directive.status == DirectiveStatus.CLOSED.value:
            return DecisionOutput(
                recommendation=DecisionRecommendation.NO_ACTION.value,
                confidence=1.0,
                summary="Directive is closed. No further action required.",
                evidence=[EvidenceItem("directive", f"status={directive.status}")],
            )

        patch: PatchProposal | None = None
        if patch_id is not None:
            patch = self._get_patch(patch_id, directive_id)
            if patch is None:
                raise DecisionNotFoundError("patch_not_in_directive")
        else:
            patch = self._latest_accepted_patch(directive_id) or self._latest_patch(directive_id)

        if patch is None:
            return DecisionOutput(
                recommendation=DecisionRecommendation.BLOCKED.value,
                confidence=0.95,
                summary="No patch proposal exists for this directive.",
                evidence=[EvidenceItem("patch_proposal", "No patches found.")],
                blocking_reasons=["no_patch_exists"],
                recommended_next_api_action="POST /agents/engineer/run or POST /patches/",
            )

        reviews = self._reviews_for_patch(patch.id)
        validations = self._validations_for_directive(directive_id)
        return self._decide_for_patch(directive, patch, reviews, validations)

    # ── Persist decision record ───────────────────────────────────────────────

    def record(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        user_id: uuid.UUID,
        patch_id: uuid.UUID | None = None,
    ) -> tuple[DecisionOutput, DecisionRecord]:
        output = self.compute(project_id, directive_id, patch_id)

        row = DecisionRecord(
            project_id=project_id,
            directive_id=directive_id,
            patch_id=patch_id,
            recommendation=output.recommendation,
            confidence=output.confidence,
            summary=output.summary,
            evidence_json=[
                {"source": e.source, "detail": e.detail, "source_id": e.source_id}
                for e in output.evidence
            ],
            blocking_reasons_json=output.blocking_reasons,
            created_by_user_id=user_id,
        )
        self._db.add(row)
        self._db.flush()

        self._audit.record(
            event_type=AuditEventType.DECISION_RECORDED,
            event_payload={
                "directive_id": str(directive_id),
                "project_id": str(project_id),
                "patch_id": str(patch_id) if patch_id else None,
                "recommendation": output.recommendation,
                "confidence": output.confidence,
                "evidence_count": len(output.evidence),
                "blocking_count": len(output.blocking_reasons),
                "decision_record_id": str(row.id),
            },
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            project_id=project_id,
            directive_id=directive_id,
        )
        self._db.flush()

        return output, row
