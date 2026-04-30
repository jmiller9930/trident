"""Simulated mutation pipeline: validate repo → lock → diff → proof → audits (100E)."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.git import git_service
from app.locks.exceptions import GitValidationError
from app.locks.lock_service import normalize_relative_file_path
from app.locks.lock_validator import assert_strict_lock_ownership, get_active_lock_or_raise
from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType, ProofObjectType
from app.models.proof_object import ProofObject
from app.models.project import Project
from app.repositories.audit_repository import AuditRepository


class SimulatedMutationPipeline:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._audit = AuditRepository(session)

    def run(
        self,
        *,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        agent_role: str,
        user_id: uuid.UUID,
        relative_file_path: str,
    ) -> dict[str, str | uuid.UUID]:
        directive = self._session.get(Directive, directive_id)
        if directive is None:
            raise ValueError("directive_not_found")
        if directive.project_id != project_id:
            raise ValueError("directive_project_mismatch")

        project = self._session.get(Project, project_id)
        if project is None:
            raise ValueError("project_not_found")

        repo_root = Path(project.allowed_root_path).expanduser().resolve()
        fp = normalize_relative_file_path(relative_file_path)

        try:
            _resolved, branch, porcelain = git_service.validate_repo_and_paths(
                repo_root=repo_root,
                relative_file_path=relative_file_path,
            )
        except GitValidationError:
            raise

        self._audit.record(
            event_type=AuditEventType.GIT_STATUS_CHECKED,
            event_payload={
                "branch": branch,
                "porcelain": porcelain,
                "repo_root": str(repo_root),
                "file_path": fp,
            },
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{agent_role.strip()}",
            workspace_id=directive.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )

        lock = get_active_lock_or_raise(self._session, project_id=project_id, file_path_normalized=fp)
        assert_strict_lock_ownership(
            lock,
            directive_id=directive_id,
            agent_role=agent_role,
            user_id=user_id,
            project_id=project_id,
            file_path_normalized=fp,
        )

        diff_text = git_service.capture_diff(repo_root)

        proof = ProofObject(
            directive_id=directive_id,
            proof_type=ProofObjectType.GIT_DIFF.value,
            proof_summary=diff_text,
            proof_uri=None,
            proof_hash=None,
            created_by_agent_role=agent_role.strip(),
        )
        self._session.add(proof)
        self._session.flush()

        self._audit.record(
            event_type=AuditEventType.DIFF_GENERATED,
            event_payload={
                "proof_object_id": str(proof.id),
                "file_path": fp,
                "diff_chars": len(diff_text),
                "branch": branch,
            },
            actor_type=AuditActorType.AGENT,
            actor_id=f"agent:{agent_role.strip()}",
            workspace_id=directive.workspace_id,
            project_id=project_id,
            directive_id=directive_id,
        )

        return {
            "proof_object_id": proof.id,
            "lock_id": lock.id,
            "branch": branch,
            "file_path": fp,
        }


__all__ = ["SimulatedMutationPipeline"]
