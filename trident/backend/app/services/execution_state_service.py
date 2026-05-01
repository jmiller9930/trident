"""ExecutionStateService — DB-derived execution state aggregate (STATUS_001).

Zero provider calls.  Zero mutations.  Read-only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.directive import Directive
from app.models.enums import DirectiveStatus, ProjectMemberRole
from app.models.git_branch_log import GitBranchLog
from app.models.git_repo_link import GitRepoLink
from app.models.patch_proposal import PatchExecutionStatus, PatchProposal, PatchProposalStatus
from app.models.project import Project
from app.models.proof_object import ProofObject
from app.models.validation_run import ValidationRun, ValidationStatus
from app.repositories.membership_repository import MembershipRepository, ROLE_RANK
from app.schemas.execution_state_schemas import (
    ActionAllowed,
    ActionsAllowed,
    BlockingReason,
    DirectiveStateSummary,
    ExecutionStateResponse,
    GitStateSummary,
    PatchStateSummary,
    SignoffStateSummary,
    ValidationStateSummary,
)


class ExecutionStateNotFoundError(ValueError):
    pass


class ExecutionStateMismatchError(ValueError):
    pass


def _allow(reason_code: str | None = None, reason_text: str | None = None) -> ActionAllowed:
    return ActionAllowed(allowed=True, reason_code=reason_code, reason_text=reason_text)


def _block(reason_code: str, reason_text: str) -> ActionAllowed:
    return ActionAllowed(allowed=False, reason_code=reason_code, reason_text=reason_text)


_ROLE_CONTRIBUTOR = ProjectMemberRole.CONTRIBUTOR.value
_ROLE_ADMIN = ProjectMemberRole.ADMIN.value


class ExecutionStateService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Directive ─────────────────────────────────────────────────────────────

    def _get_directive(self, directive_id: uuid.UUID, project_id: uuid.UUID) -> Directive:
        d = self._db.get(Directive, directive_id)
        if d is None:
            raise ExecutionStateNotFoundError("directive_not_found")
        if d.project_id != project_id:
            raise ExecutionStateMismatchError("directive_not_in_project")
        return d

    # ── Git ───────────────────────────────────────────────────────────────────

    def _git_summary(self, directive: Directive) -> GitStateSummary:
        link = self._db.scalars(
            select(GitRepoLink).where(GitRepoLink.project_id == directive.project_id)
        ).first()

        if link is None:
            return GitStateSummary(repo_linked=False)

        proj = self._db.get(Project, directive.project_id)
        commit_sha = proj.git_commit_sha if proj else None

        branch_created_row = self._db.scalars(
            select(GitBranchLog)
            .where(
                GitBranchLog.project_id == directive.project_id,
                GitBranchLog.directive_id == directive.id,
                GitBranchLog.event_type == "branch_created",
            )
            .order_by(GitBranchLog.created_at.desc())
            .limit(1)
        ).first()

        commit_pushed_row = self._db.scalars(
            select(GitBranchLog)
            .where(
                GitBranchLog.project_id == directive.project_id,
                GitBranchLog.directive_id == directive.id,
                GitBranchLog.event_type == "commit_pushed",
            )
            .order_by(GitBranchLog.created_at.desc())
            .limit(1)
        ).first()

        branch_name = branch_created_row.branch_name if branch_created_row else None

        return GitStateSummary(
            repo_linked=True,
            provider=link.provider,
            owner=link.owner,
            repo_name=link.repo_name,
            branch_name=branch_name,
            latest_commit_sha=commit_pushed_row.commit_sha if commit_pushed_row else commit_sha,
            branch_created=branch_created_row is not None,
            commit_pushed=commit_pushed_row is not None,
        )

    # ── Patches ───────────────────────────────────────────────────────────────

    def _patch_summary(self, directive_id: uuid.UUID) -> PatchStateSummary:
        rows = list(self._db.scalars(
            select(PatchProposal)
            .where(PatchProposal.directive_id == directive_id)
            .order_by(PatchProposal.created_at.desc())
        ).all())

        if not rows:
            return PatchStateSummary()

        accepted = next(
            (r for r in rows if r.status == PatchProposalStatus.ACCEPTED.value), None
        )
        latest = rows[0]

        return PatchStateSummary(
            patch_count=len(rows),
            latest_patch_id=latest.id,
            latest_patch_status=latest.status,
            accepted_patch_id=accepted.id if accepted else None,
            accepted_patch_executed=(
                accepted is not None
                and accepted.execution_status == PatchExecutionStatus.EXECUTED.value
            ),
            execution_commit_sha=accepted.execution_commit_sha if accepted else None,
        )

    # ── Validations ───────────────────────────────────────────────────────────

    def _validation_summary(self, directive_id: uuid.UUID) -> ValidationStateSummary:
        rows = list(self._db.scalars(
            select(ValidationRun)
            .where(ValidationRun.directive_id == directive_id)
            .order_by(ValidationRun.created_at.desc())
        ).all())

        if not rows:
            return ValidationStateSummary(signoff_eligible=False)

        passed = sum(1 for r in rows if r.status == ValidationStatus.PASSED.value)
        failed = sum(1 for r in rows if r.status == ValidationStatus.FAILED.value)
        waived = sum(1 for r in rows if r.status == ValidationStatus.WAIVED.value)

        eligible = passed > 0 and failed == 0
        latest = rows[0]

        return ValidationStateSummary(
            validation_count=len(rows),
            passed_count=passed,
            failed_count=failed,
            waived_count=waived,
            latest_validation_status=latest.status,
            signoff_eligible=eligible,
        )

    # ── Signoff ───────────────────────────────────────────────────────────────

    def _signoff_summary(self, directive: Directive) -> SignoffStateSummary:
        if directive.status != DirectiveStatus.CLOSED.value:
            return SignoffStateSummary(closed=False)

        proof = self._db.scalars(
            select(ProofObject)
            .where(
                ProofObject.directive_id == directive.id,
                ProofObject.proof_type == "DIRECTIVE_SIGNOFF",
            )
            .order_by(ProofObject.created_at.desc())
            .limit(1)
        ).first()

        return SignoffStateSummary(
            closed=True,
            proof_object_id=proof.id if proof else None,
        )

    # ── Role check helper ─────────────────────────────────────────────────────

    def _user_role(self, user_id: uuid.UUID, project_id: uuid.UUID) -> str | None:
        try:
            m = MembershipRepository(self._db).get_membership(user_id, project_id)
            return m.role if m else None
        except Exception:
            return None

    def _at_least(self, role: str | None, minimum: str) -> bool:
        return bool(role and ROLE_RANK.get(role, 0) >= ROLE_RANK.get(minimum, 99))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _compute_actions(
        self,
        directive: Directive,
        git: GitStateSummary,
        patch: PatchStateSummary,
        validation: ValidationStateSummary,
        signoff: SignoffStateSummary,
        role: str | None,
    ) -> ActionsAllowed:
        is_closed = signoff.closed
        is_issued = directive.status == DirectiveStatus.ISSUED.value
        is_contributor = self._at_least(role, _ROLE_CONTRIBUTOR)
        is_admin = self._at_least(role, _ROLE_ADMIN)

        def _if_closed(then: ActionAllowed) -> ActionAllowed:
            return _block("directive_closed", "Directive is closed and no longer accepts changes") if is_closed else then

        # create_patch
        create_patch = _if_closed(
            _allow() if is_contributor else _block("insufficient_role", "CONTRIBUTOR or higher required")
        )

        # accept_patch / reject_patch — require a PROPOSED patch and ADMIN
        has_proposed = patch.patch_count > 0 and patch.latest_patch_status == PatchProposalStatus.PROPOSED.value
        accept_patch = _if_closed(
            _allow() if (has_proposed and is_admin)
            else _block("insufficient_role", "ADMIN required") if not is_admin
            else _block("no_proposed_patch", "No patch in PROPOSED state to accept")
        )
        reject_patch = _if_closed(
            _allow() if (has_proposed and is_admin)
            else _block("insufficient_role", "ADMIN required") if not is_admin
            else _block("no_proposed_patch", "No patch in PROPOSED state to reject")
        )

        # execute_patch
        if is_closed:
            execute_patch = _block("directive_closed", "Directive is closed")
        elif not git.repo_linked:
            execute_patch = _block("no_repo_linked", "Project has no linked Git repository")
        elif not git.branch_created:
            execute_patch = _block("no_branch", "Directive branch has not been created yet")
        elif patch.accepted_patch_id is None:
            execute_patch = _block("no_accepted_patch", "No accepted patch available to execute")
        elif patch.accepted_patch_executed:
            execute_patch = _block("patch_already_executed", "Accepted patch has already been executed")
        elif not is_admin:
            execute_patch = _block("insufficient_role", "ADMIN required to execute patches")
        else:
            execute_patch = _allow()

        # create_validation
        create_validation = _if_closed(
            _allow() if (is_issued and is_contributor)
            else _block("directive_not_issued", "Directive must be ISSUED to create validations") if not is_issued
            else _block("insufficient_role", "CONTRIBUTOR or higher required")
        )

        # start_validation
        start_validation = _if_closed(
            _allow() if (is_issued and is_contributor and validation.validation_count > 0)
            else _block("directive_not_issued", "Directive must be ISSUED") if not is_issued
            else _block("insufficient_role", "CONTRIBUTOR required") if not is_contributor
            else _block("no_validation_run", "Create a validation run first")
        )

        # complete_validation
        complete_validation = _if_closed(
            _allow() if (is_issued and is_admin and validation.validation_count > 0)
            else _block("directive_not_issued", "Directive must be ISSUED") if not is_issued
            else _block("insufficient_role", "ADMIN required to complete validations") if not is_admin
            else _block("no_validation_run", "Create a validation run first")
        )

        # waive_validation
        waive_validation = _if_closed(
            _allow() if (is_issued and is_admin and validation.validation_count > 0)
            else _block("directive_not_issued", "Directive must be ISSUED") if not is_issued
            else _block("insufficient_role", "ADMIN required to waive validations") if not is_admin
            else _block("no_validation_run", "Create a validation run first")
        )

        # signoff
        if is_closed:
            signoff_action = _block("directive_closed", "Directive is already closed")
        elif not is_issued:
            signoff_action = _block("directive_not_issued", f"Directive must be ISSUED (currently {directive.status})")
        elif validation.validation_count == 0:
            signoff_action = _block("no_validation_runs", "At least one passed validation is required for sign-off")
        elif validation.passed_count == 0:
            signoff_action = _block("no_passed_validations", "At least one PASSED validation is required")
        elif validation.failed_count > 0:
            signoff_action = _block("unwaived_failure", f"{validation.failed_count} FAILED validation(s) must be waived before sign-off")
        elif not is_admin:
            signoff_action = _block("insufficient_role", "ADMIN required to sign off a directive")
        else:
            signoff_action = _allow()

        return ActionsAllowed(
            create_patch=create_patch,
            accept_patch=accept_patch,
            reject_patch=reject_patch,
            execute_patch=execute_patch,
            create_validation=create_validation,
            start_validation=start_validation,
            complete_validation=complete_validation,
            waive_validation=waive_validation,
            signoff=signoff_action,
        )

    # ── Blocking reasons ──────────────────────────────────────────────────────

    def _compute_blocking_reasons(
        self,
        directive: Directive,
        git: GitStateSummary,
        patch: PatchStateSummary,
        validation: ValidationStateSummary,
        signoff: SignoffStateSummary,
    ) -> list[BlockingReason]:
        reasons: list[BlockingReason] = []

        if signoff.closed:
            reasons.append(BlockingReason(
                code="directive_closed",
                message="Directive has been signed off and closed.",
                required_next_action=None,
            ))
            return reasons

        if not git.repo_linked:
            reasons.append(BlockingReason(
                code="no_repo_linked",
                message="No Git repository is linked to this project.",
                required_next_action="Link a repository via POST /git/link-repo or POST /git/create-repo",
            ))
        elif not git.branch_created:
            reasons.append(BlockingReason(
                code="no_directive_branch",
                message="A Git branch has not been created for this directive.",
                required_next_action="Issue the directive to auto-create a branch, or POST /git/create-branch",
            ))

        if patch.accepted_patch_id is None and patch.patch_count > 0:
            reasons.append(BlockingReason(
                code="no_accepted_patch",
                message="Patches exist but none have been accepted yet.",
                required_next_action="Accept a patch via PATCH /patches/{patch_id}/accept",
            ))

        if patch.accepted_patch_id is not None and not patch.accepted_patch_executed:
            reasons.append(BlockingReason(
                code="patch_not_executed",
                message="An accepted patch is ready for execution but has not been pushed to the branch.",
                required_next_action="Execute via POST /patches/{patch_id}/execute",
            ))

        if validation.validation_count == 0:
            reasons.append(BlockingReason(
                code="no_validations",
                message="No validation runs have been recorded for this directive.",
                required_next_action="Create a validation run via POST /validations/",
            ))
        elif validation.passed_count == 0:
            reasons.append(BlockingReason(
                code="no_passed_validation",
                message="No validation run has PASSED yet.",
                required_next_action="Complete a validation run with passed=true",
            ))

        if validation.failed_count > 0:
            reasons.append(BlockingReason(
                code="unwaived_validation_failure",
                message=f"{validation.failed_count} validation run(s) have FAILED and have not been waived.",
                required_next_action="Waive failed runs via POST /validations/{run_id}/waive, or investigate failures",
            ))

        return reasons

    # ── Public entry point ────────────────────────────────────────────────────

    def get_execution_state(
        self,
        directive_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ExecutionStateResponse:
        directive = self._get_directive(directive_id, project_id)
        role = self._user_role(user_id, project_id)

        git = self._git_summary(directive)
        patch = self._patch_summary(directive_id)
        validation = self._validation_summary(directive_id)
        signoff_sum = self._signoff_summary(directive)

        actions = self._compute_actions(directive, git, patch, validation, signoff_sum, role)
        blocking = self._compute_blocking_reasons(directive, git, patch, validation, signoff_sum)

        return ExecutionStateResponse(
            directive=DirectiveStateSummary(
                directive_id=directive.id,
                project_id=directive.project_id,
                title=directive.title,
                status=directive.status,
                created_by_user_id=directive.created_by_user_id,
                created_at=directive.created_at,
                closed_at=directive.closed_at,
                closed_by_user_id=directive.closed_by_user_id,
            ),
            git=git,
            patch=patch,
            validation=validation,
            signoff=signoff_sum,
            actions_allowed=actions,
            blocking_reasons=blocking,
            computed_at=datetime.now(timezone.utc),
        )
