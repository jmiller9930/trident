"""DirectiveStateService — aggregates directive state for the VS Code workbench (STATUS_001).

Single authoritative read path: never modifies state.
Queries five domains: directive, git, patches, validations, signoff eligibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.git_provider.branch_naming import directive_branch_name as _make_branch_name
from app.models.directive import Directive
from app.models.enums import DirectiveStatus, ProjectMemberRole
from app.models.git_branch_log import GitBranchLog
from app.models.git_repo_link import GitRepoLink
from app.models.patch_proposal import PatchExecutionStatus, PatchProposal, PatchProposalStatus
from app.models.project import Project
from app.models.validation_run import ValidationRun, ValidationStatus
from app.repositories.membership_repository import MembershipRepository
from app.schemas.directive_state import (
    AllowedAction,
    DirectiveCoreSummary,
    DirectiveStateResponse,
    GitState,
    PatchStateSummary,
    SignoffState,
    ValidationStateSummary,
    lifecycle_phase,
)
from app.services.signoff_service import SignoffService, ValidationSummary


class DirectiveNotFoundError(ValueError):
    pass


class DirectiveProjectMismatchError(ValueError):
    pass


class DirectiveStateService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Directive ─────────────────────────────────────────────────────────────

    def _get_directive(self, directive_id: uuid.UUID, project_id: uuid.UUID) -> Directive:
        d = self._db.get(Directive, directive_id)
        if d is None:
            raise DirectiveNotFoundError("directive_not_found")
        if d.project_id != project_id:
            raise DirectiveProjectMismatchError("directive_not_in_project")
        return d

    # ── Git ───────────────────────────────────────────────────────────────────

    def _git_state(self, directive: Directive) -> GitState:
        proj = self._db.get(Project, directive.project_id)
        link = self._db.scalars(
            select(GitRepoLink).where(GitRepoLink.project_id == directive.project_id)
        ).first()

        if link is None:
            return GitState(repo_linked=False)

        expected_branch = _make_branch_name(directive.id, directive.title)
        branch_log = self._db.scalars(
            select(GitBranchLog).where(
                GitBranchLog.project_id == directive.project_id,
                GitBranchLog.directive_id == directive.id,
                GitBranchLog.event_type == "branch_created",
            ).order_by(GitBranchLog.created_at.desc()).limit(1)
        ).first()

        return GitState(
            repo_linked=True,
            clone_url=link.clone_url,
            default_branch=link.default_branch,
            active_branch=proj.git_branch if proj else None,
            commit_sha=proj.git_commit_sha if proj else None,
            branch_created_for_directive=branch_log is not None,
            directive_branch_name=branch_log.branch_name if branch_log else expected_branch,
        )

    # ── Patches ───────────────────────────────────────────────────────────────

    def _patch_state(self, directive_id: uuid.UUID) -> PatchStateSummary:
        rows = list(self._db.scalars(
            select(PatchProposal)
            .where(PatchProposal.directive_id == directive_id)
            .order_by(PatchProposal.created_at.desc())
        ).all())

        if not rows:
            return PatchStateSummary()

        counts = {s: 0 for s in ("PROPOSED", "ACCEPTED", "REJECTED")}
        executed_count = 0
        for r in rows:
            if r.status in counts:
                counts[r.status] += 1
            if r.execution_status == PatchExecutionStatus.EXECUTED.value:
                executed_count += 1

        latest = rows[0]
        return PatchStateSummary(
            total=len(rows),
            proposed=counts["PROPOSED"],
            accepted=counts["ACCEPTED"],
            rejected=counts["REJECTED"],
            executed=executed_count,
            latest_patch_id=latest.id,
            latest_patch_status=latest.status,
            latest_patch_title=latest.title,
            latest_execution_commit_sha=latest.execution_commit_sha,
            latest_execution_branch_name=latest.execution_branch_name,
        )

    # ── Validations ───────────────────────────────────────────────────────────

    def _validation_state(self, directive_id: uuid.UUID) -> ValidationStateSummary:
        rows = list(self._db.scalars(
            select(ValidationRun)
            .where(ValidationRun.directive_id == directive_id)
            .order_by(ValidationRun.created_at.desc())
        ).all())

        if not rows:
            return ValidationStateSummary()

        counts: dict[str, int] = {s.value: 0 for s in ValidationStatus}
        for r in rows:
            counts[r.status] = counts.get(r.status, 0) + 1

        latest = rows[0]
        return ValidationStateSummary(
            total=len(rows),
            pending=counts.get("PENDING", 0),
            running=counts.get("RUNNING", 0),
            passed=counts.get("PASSED", 0),
            failed=counts.get("FAILED", 0),
            waived=counts.get("WAIVED", 0),
            latest_run_id=latest.id,
            latest_run_status=latest.status,
            latest_run_type=latest.validation_type,
        )

    # ── Signoff ───────────────────────────────────────────────────────────────

    def _signoff_state(self, directive: Directive, v_summary: ValidationSummary) -> SignoffState:
        if directive.status == DirectiveStatus.CLOSED.value:
            return SignoffState(eligible=False, blocking_reasons=["directive_already_closed"])

        if directive.status != DirectiveStatus.ISSUED.value:
            return SignoffState(
                eligible=False,
                blocking_reasons=[f"directive_not_issued:status={directive.status}"]
            )

        reason = v_summary.eligibility_reason()
        if reason:
            return SignoffState(eligible=False, blocking_reasons=[reason])
        return SignoffState(eligible=True)

    # ── Allowed actions (role-aware) ──────────────────────────────────────────

    def _allowed_actions(
        self,
        directive: Directive,
        user_id: uuid.UUID,
        git: GitState,
        patches: PatchStateSummary,
        validations: ValidationStateSummary,
        signoff: SignoffState,
    ) -> list[AllowedAction]:
        mrepo = MembershipRepository(self._db)
        try:
            membership = mrepo.get_membership(user_id, directive.project_id)
            role = membership.role if membership else None
        except Exception:
            role = None

        from app.repositories.membership_repository import ROLE_RANK

        def _has_role(minimum: str) -> bool:
            return bool(role and ROLE_RANK.get(role, 0) >= ROLE_RANK.get(minimum, 99))

        is_closed = directive.status == DirectiveStatus.CLOSED.value
        is_issued = directive.status == DirectiveStatus.ISSUED.value

        actions: list[AllowedAction] = []

        # Issue directive
        actions.append(AllowedAction(
            action="issue",
            label="Issue Directive",
            enabled=(directive.status == "DRAFT" and _has_role("CONTRIBUTOR")),
            disabled_reason=None if (directive.status == "DRAFT" and _has_role("CONTRIBUTOR"))
            else ("directive_not_draft" if directive.status != "DRAFT" else "insufficient_role"),
        ))

        # Create patch
        actions.append(AllowedAction(
            action="create_patch",
            label="Create Patch",
            enabled=(not is_closed and _has_role("CONTRIBUTOR")),
            disabled_reason="directive_closed" if is_closed else (
                None if _has_role("CONTRIBUTOR") else "insufficient_role"
            ),
        ))

        # Execute latest accepted patch
        has_executable = (
            patches.total > 0
            and patches.latest_patch_status == PatchProposalStatus.ACCEPTED.value
            and not is_closed
        )
        actions.append(AllowedAction(
            action="execute_patch",
            label="Execute Accepted Patch",
            enabled=(has_executable and git.repo_linked and git.branch_created_for_directive and _has_role("ADMIN")),
            disabled_reason=None if has_executable else (
                "directive_closed" if is_closed
                else "no_accepted_patch" if patches.latest_patch_status != PatchProposalStatus.ACCEPTED.value
                else "repo_not_linked" if not git.repo_linked
                else None
            ),
        ))

        # Create validation run
        actions.append(AllowedAction(
            action="create_validation",
            label="Create Validation Run",
            enabled=(is_issued and not is_closed and _has_role("CONTRIBUTOR")),
            disabled_reason="directive_closed" if is_closed else (
                "directive_not_issued" if not is_issued else (
                    None if _has_role("CONTRIBUTOR") else "insufficient_role"
                )
            ),
        ))

        # Signoff
        actions.append(AllowedAction(
            action="signoff",
            label="Sign Off Directive",
            enabled=(signoff.eligible and _has_role("ADMIN")),
            disabled_reason=None if (signoff.eligible and _has_role("ADMIN")) else (
                "directive_closed" if is_closed
                else "; ".join(signoff.blocking_reasons) if not signoff.eligible
                else "insufficient_role"
            ),
        ))

        return actions

    # ── Public entry point ────────────────────────────────────────────────────

    def get_state(self, directive_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID) -> DirectiveStateResponse:
        directive = self._get_directive(directive_id, project_id)

        git = self._git_state(directive)
        patches = self._patch_state(directive_id)
        v_state = self._validation_state(directive_id)

        # Compute validation summary for signoff eligibility (reuses SignoffService helper)
        v_summary = SignoffService(self._db)._validation_summary(directive_id)
        signoff = self._signoff_state(directive, v_summary)

        allowed = self._allowed_actions(directive, user_id, git, patches, v_state, signoff)

        return DirectiveStateResponse(
            directive=DirectiveCoreSummary(
                id=directive.id,
                title=directive.title,
                status=directive.status,
                workspace_id=directive.workspace_id,
                project_id=directive.project_id,
                created_by_user_id=directive.created_by_user_id,
                created_at=directive.created_at,
                updated_at=directive.updated_at,
                closed_at=directive.closed_at,
                closed_by_user_id=directive.closed_by_user_id,
            ),
            lifecycle_phase=lifecycle_phase(directive.status),
            git=git,
            patches=patches,
            validations=v_state,
            signoff=signoff,
            allowed_actions=allowed,
            as_of=datetime.now(timezone.utc),
        )
