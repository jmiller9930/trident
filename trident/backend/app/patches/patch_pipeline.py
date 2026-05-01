"""100M — unified diff proposal + server-verified apply recording."""

from __future__ import annotations

import difflib
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.git import git_service
from app.locks.exceptions import GitValidationError, LockNotFoundError, LockOwnershipError
from app.locks.lock_service import LockService, normalize_relative_file_path
from app.locks.lock_validator import assert_strict_lock_ownership, get_active_lock_or_raise
from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType, ProofObjectType
from app.models.proof_object import ProofObject
from app.models.project import Project
from app.repositories.audit_repository import AuditRepository


def assert_patch_path_no_hidden_segments(relative_file_path: str) -> str:
    """100M §14 — reject paths that touch hidden segments (.git, dotfiles)."""
    fp = normalize_relative_file_path(relative_file_path)
    for segment in fp.split("/"):
        if segment.startswith("."):
            raise ValueError("hidden_path_segment_forbidden")
    return fp


def build_unified_diff(*, display_path: str, before: str, after: str) -> str:
    """Unified diff with stable a/ b/ prefixes (directive §6)."""
    a = before.splitlines(keepends=True)
    b = after.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            a,
            b,
            fromfile=f"a/{display_path}",
            tofile=f"b/{display_path}",
            lineterm="\n",
        )
    )


class PatchWorkflowService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._audit = AuditRepository(session)

    def propose(
        self,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        agent_role: str,
        user_id: uuid.UUID,
        relative_file_path: str,
        before_text: str,
        after_text: str,
        correlation_id: uuid.UUID | None = None,
    ) -> tuple[str, str, uuid.UUID]:
        fp = assert_patch_path_no_hidden_segments(relative_file_path)
        directive = self._session.get(Directive, directive_id)
        if directive is None:
            raise ValueError("directive_not_found")
        if directive.project_id != project_id:
            raise ValueError("directive_project_mismatch")
        project = self._session.get(Project, project_id)
        if project is None:
            raise ValueError("project_not_found")

        repo_root = Path(project.allowed_root_path).expanduser().resolve()
        try:
            git_service.validate_repo_and_paths(repo_root=repo_root, relative_file_path=relative_file_path)
        except GitValidationError:
            raise

        cid = correlation_id or uuid.uuid4()
        diff_text = build_unified_diff(display_path=fp, before=before_text, after=after_text)
        summary = f"{len(before_text)}→{len(after_text)} chars; {diff_text.count(chr(10))} diff lines"

        self._audit.record(
            event_type=AuditEventType.PATCH_PROPOSED,
            event_payload={
                "correlation_id": str(cid),
                "file_path": fp,
                "summary": summary,
                "diff_chars": len(diff_text),
                "user_id": str(user_id),
            },
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{agent_role.strip()}",
            workspace_id=directive.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )
        self._session.flush()
        return diff_text, summary, cid

    def reject(
        self,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        agent_role: str,
        user_id: uuid.UUID,
        relative_file_path: str,
        reason: str | None,
        correlation_id: uuid.UUID | None,
    ) -> uuid.UUID:
        fp = assert_patch_path_no_hidden_segments(relative_file_path)
        directive = self._session.get(Directive, directive_id)
        if directive is None:
            raise ValueError("directive_not_found")
        if directive.project_id != project_id:
            raise ValueError("directive_project_mismatch")

        cid = correlation_id or uuid.uuid4()
        self._audit.record(
            event_type=AuditEventType.PATCH_REJECTED,
            event_payload={
                "correlation_id": str(cid),
                "file_path": fp,
                "reason": (reason or "").strip()[:2048],
            },
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            workspace_id=directive.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )
        self._session.flush()
        return cid

    def apply_complete(
        self,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        agent_role: str,
        user_id: uuid.UUID,
        relative_file_path: str,
        unified_diff: str,
        after_text: str,
        correlation_id: uuid.UUID | None,
    ) -> dict[str, uuid.UUID | str]:
        fp = assert_patch_path_no_hidden_segments(relative_file_path)
        directive = self._session.get(Directive, directive_id)
        if directive is None:
            raise ValueError("directive_not_found")
        if directive.project_id != project_id:
            raise ValueError("directive_project_mismatch")

        project = self._session.get(Project, project_id)
        if project is None:
            raise ValueError("project_not_found")

        repo_root = Path(project.allowed_root_path).expanduser().resolve()
        try:
            resolved, branch, porcelain = git_service.validate_repo_and_paths(
                repo_root=repo_root,
                relative_file_path=relative_file_path,
            )
        except GitValidationError:
            raise

        LockService(self._session, self._settings)._expire_stale_locks_for_path(project_id=project_id, fp=fp)

        self._audit.record(
            event_type=AuditEventType.GIT_STATUS_CHECKED,
            event_payload={
                "branch": branch,
                "porcelain": porcelain,
                "repo_root": str(repo_root),
                "file_path": fp,
                "phase": "patch_apply_complete",
            },
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{agent_role.strip()}",
            workspace_id=directive.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )

        disk_text = resolved.read_text(encoding="utf-8")
        if disk_text != after_text:
            raise ValueError("patch_disk_verification_failed")

        lock = get_active_lock_or_raise(
            self._session,
            project_id=project_id,
            file_path_normalized=fp,
            settings=self._settings,
        )
        assert_strict_lock_ownership(
            lock,
            directive_id=directive_id,
            agent_role=agent_role,
            user_id=user_id,
            project_id=project_id,
            file_path_normalized=fp,
            require_active_for_editing=True,
        )

        cid = correlation_id or uuid.uuid4()
        proof = ProofObject(
            directive_id=directive_id,
            proof_type=ProofObjectType.GIT_DIFF.value,
            proof_summary=unified_diff,
            proof_uri=None,
            proof_hash=None,
            created_by_agent_role=agent_role.strip(),
        )
        self._session.add(proof)
        self._session.flush()

        self._audit.record(
            event_type=AuditEventType.PATCH_APPLIED,
            event_payload={
                "correlation_id": str(cid),
                "proof_object_id": str(proof.id),
                "file_path": fp,
                "lock_id": str(lock.id),
                "branch": branch,
            },
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{agent_role.strip()}",
            workspace_id=directive.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )
        self._session.flush()

        return {"proof_object_id": proof.id, "lock_id": lock.id, "correlation_id": cid}


__all__ = ["PatchWorkflowService", "assert_patch_path_no_hidden_segments", "build_unified_diff"]
