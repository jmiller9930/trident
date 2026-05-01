"""GitProjectService — business logic for GitHub repo/branch operations (GITHUB_003).

Rules:
- Always call GitProvider interface; never import GitHubClient directly.
- Token never appears in return values, audit payloads, or exceptions.
- All mutations are atomic within the session (caller commits).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.git_provider.base import GitProvider, GitProviderError, RepoInfo
from app.git_provider.branch_naming import directive_branch_name, validate_trident_branch_name
from app.models.directive import Directive
from app.models.enums import AuditActorType, AuditEventType
from app.models.git_branch_log import GIT_BRANCH_LOG_EVENTS, GitBranchLog
from app.models.git_repo_link import GitRepoLink
from app.models.project import Project
from app.repositories.audit_repository import AuditRepository
from app.models.enums import AgentRole as _AgentRole
from app.models.proof_object import ProofObject
from app.schemas.git_schemas import (
    GitCreateBranchRequest,
    GitCreateBranchResponse,
    GitCreateRepoRequest,
    GitCreateRepoResponse,
    GitLinkRepoRequest,
    GitLinkRepoResponse,
    GitPushFilesRequest,
    GitPushFilesResponse,
    GitRepoStatusResponse,
    GitBranchListResponse,
    GitBranchResponse,
)

_FILE_PATH_INVALID_PATTERNS = ("..", "//")


def _validate_file_paths(files: list) -> str | None:
    """Return error string if any path is unsafe, else None."""
    for f in files:
        path = f.path.strip()
        if not path:
            return "empty_file_path"
        if path.startswith("/"):
            return f"absolute_path_forbidden:{path[:80]}"
        if "\\" in path or ".." in path:
            return f"path_traversal_forbidden:{path[:80]}"
        if "//" in path:
            return f"invalid_path:{path[:80]}"
    return None

_TRIDENT_README = """\
# {name}

Managed by [Trident](https://github.com/your-org/trident).

---

*This repository was initialized by the Trident control plane.*
"""

_TRIDENT_GITIGNORE = """\
# Python
__pycache__/
*.py[cod]
.env
*.egg-info/
dist/
build/
.venv/
venv/

# Node
node_modules/
.next/
dist/

# Secrets — never commit
*.pem
*.key
*.p12
*.pfx
*.p8
.env.local
.env.production
.env.*.local
secrets/
"""


class GitAlreadyLinkedError(ValueError):
    pass


class GitNotLinkedError(ValueError):
    pass


class GitDirectiveMismatchError(ValueError):
    pass


class GitInvalidBranchNameError(ValueError):
    pass


class GitProjectService:
    """Repo/branch operations, persistence, and audit emission for a Trident project."""

    def __init__(self, db: Session, *, provider: GitProvider) -> None:
        self._db = db
        self._provider = provider
        self._audit = AuditRepository(db)

    # ── Read helpers ─────────────────────────────────────────────────────────

    def _get_project(self, project_id: uuid.UUID) -> Project:
        proj = self._db.get(Project, project_id)
        if proj is None:
            raise ValueError("project_not_found")
        return proj

    def _get_repo_link(self, project_id: uuid.UUID) -> GitRepoLink | None:
        return self._db.scalars(
            select(GitRepoLink).where(GitRepoLink.project_id == project_id)
        ).first()

    def _require_repo_link(self, project_id: uuid.UUID) -> GitRepoLink:
        link = self._get_repo_link(project_id)
        if link is None:
            raise GitNotLinkedError("repo_not_linked")
        return link

    def _require_no_repo_link(self, project_id: uuid.UUID) -> None:
        if self._get_repo_link(project_id) is not None:
            raise GitAlreadyLinkedError("repo_already_linked")

    # ── Repo link persistence ─────────────────────────────────────────────────

    def _persist_repo_link(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        info: RepoInfo,
    ) -> GitRepoLink:
        link = GitRepoLink(
            project_id=project_id,
            provider=info.provider,
            owner=info.owner,
            repo_name=info.repo_name,
            clone_url=info.clone_url,
            html_url=info.html_url,
            default_branch=info.default_branch,
            private=info.private,
            linked_by_user_id=user_id,
            linked_at=datetime.now(timezone.utc),
        )
        self._db.add(link)
        return link

    def _update_project_git_fields(
        self,
        proj: Project,
        *,
        info: RepoInfo,
        commit_sha: str | None,
    ) -> None:
        proj.git_remote_url = info.clone_url
        proj.git_branch = info.default_branch
        if commit_sha:
            proj.git_commit_sha = commit_sha

    # ── Audit helpers ─────────────────────────────────────────────────────────

    def _emit_audit(
        self,
        event_type: AuditEventType,
        *,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> None:
        self._audit.record(
            event_type=event_type,
            event_payload=payload,
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            project_id=project_id,
        )

    # ── Public operations ─────────────────────────────────────────────────────

    def create_repo(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        body: GitCreateRepoRequest,
    ) -> GitCreateRepoResponse:
        self._require_no_repo_link(project_id)
        proj = self._get_project(project_id)

        repo_name = body.name or proj.name.lower().replace(" ", "-").replace("_", "-")[:100]

        info = self._provider.create_repo(
            name=repo_name,
            description=body.description or (proj.description or ""),
            private=body.private,
            org=body.org,
        )

        commit_sha: str | None = None
        if body.init_scaffold:
            commit_result = self._provider.push_files(
                owner=info.owner,
                repo_name=info.repo_name,
                branch_name=info.default_branch,
                files={
                    "README.md": _TRIDENT_README.format(name=repo_name),
                    ".gitignore": _TRIDENT_GITIGNORE,
                },
                message="chore: Trident scaffold initialization",
            )
            commit_sha = commit_result.sha

        if commit_sha is None:
            try:
                commit_sha = self._provider.get_default_branch_sha(
                    owner=info.owner, repo_name=info.repo_name
                )
            except GitProviderError:
                commit_sha = None

        self._persist_repo_link(project_id=project_id, user_id=user_id, info=info)
        self._update_project_git_fields(proj, info=info, commit_sha=commit_sha)
        self._db.flush()

        self._emit_audit(
            AuditEventType.GIT_REPO_CREATED,
            user_id=user_id,
            project_id=project_id,
            payload={
                "provider": info.provider,
                "owner": info.owner,
                "repo_name": info.repo_name,
                "clone_url": info.clone_url,
                "private": info.private,
                "init_scaffold": body.init_scaffold,
                "commit_sha": commit_sha,
            },
        )

        return GitCreateRepoResponse(
            provider=info.provider,
            owner=info.owner,
            repo_name=info.repo_name,
            clone_url=info.clone_url,
            html_url=info.html_url,
            default_branch=info.default_branch,
            private=info.private,
            created=True,
            git_commit_sha=commit_sha,
        )

    def link_repo(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        body: GitLinkRepoRequest,
    ) -> GitLinkRepoResponse:
        self._require_no_repo_link(project_id)
        proj = self._get_project(project_id)

        info = self._provider.link_repo(clone_url=body.clone_url)

        try:
            commit_sha = self._provider.get_default_branch_sha(
                owner=info.owner, repo_name=info.repo_name
            )
        except GitProviderError:
            commit_sha = None

        self._persist_repo_link(project_id=project_id, user_id=user_id, info=info)
        self._update_project_git_fields(proj, info=info, commit_sha=commit_sha)
        self._db.flush()

        self._emit_audit(
            AuditEventType.GIT_REPO_LINKED,
            user_id=user_id,
            project_id=project_id,
            payload={
                "provider": info.provider,
                "owner": info.owner,
                "repo_name": info.repo_name,
                "clone_url": info.clone_url,
                "commit_sha": commit_sha,
            },
        )

        return GitLinkRepoResponse(
            provider=info.provider,
            owner=info.owner,
            repo_name=info.repo_name,
            clone_url=info.clone_url,
            html_url=info.html_url,
            default_branch=info.default_branch,
            private=info.private,
            git_commit_sha=commit_sha,
        )

    def get_repo_status(
        self,
        project_id: uuid.UUID,
    ) -> GitRepoStatusResponse:
        link = self._require_repo_link(project_id)
        proj = self._get_project(project_id)
        return GitRepoStatusResponse(
            provider=link.provider,
            owner=link.owner,
            repo_name=link.repo_name,
            clone_url=link.clone_url,
            html_url=link.html_url,
            default_branch=link.default_branch,
            current_git_branch=proj.git_branch,
            current_git_commit_sha=proj.git_commit_sha,
            private=link.private,
            linked_at=link.linked_at,
            linked_by_user_id=link.linked_by_user_id,
        )

    def create_branch(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        body: GitCreateBranchRequest,
    ) -> GitCreateBranchResponse:
        link = self._require_repo_link(project_id)
        proj = self._get_project(project_id)

        # Validate directive belongs to same project
        directive_id = body.directive_id
        if directive_id is not None:
            directive = self._db.get(Directive, directive_id)
            if directive is None or directive.project_id != project_id:
                raise GitDirectiveMismatchError("directive_not_in_project")

        # Resolve branch name
        branch_name = body.branch_name
        if not branch_name:
            if directive_id is not None:
                title = ""
                if directive is not None:
                    title = directive.title
                branch_name = directive_branch_name(directive_id, title)
            else:
                raise GitInvalidBranchNameError("branch_name_required_without_directive_id")

        # Validate Trident-generated names follow the convention
        if body.branch_name is None and not validate_trident_branch_name(branch_name):
            raise GitInvalidBranchNameError(f"invalid_trident_branch_name:{branch_name}")

        # Resolve from_sha
        from_sha = body.from_sha or proj.git_commit_sha
        if not from_sha:
            from_sha = self._provider.get_default_branch_sha(
                owner=link.owner, repo_name=link.repo_name
            )

        branch_info = self._provider.create_branch(
            owner=link.owner,
            repo_name=link.repo_name,
            branch_name=branch_name,
            from_sha=from_sha,
        )

        log_row = GitBranchLog(
            project_id=project_id,
            directive_id=directive_id,
            provider=link.provider,
            branch_name=branch_name,
            commit_sha=branch_info.commit_sha,
            commit_message=None,
            created_by_user_id=user_id,
            event_type="branch_created",
        )
        self._db.add(log_row)
        self._db.flush()

        self._emit_audit(
            AuditEventType.GIT_BRANCH_CREATED,
            user_id=user_id,
            project_id=project_id,
            payload={
                "provider": link.provider,
                "owner": link.owner,
                "repo_name": link.repo_name,
                "branch_name": branch_name,
                "commit_sha": branch_info.commit_sha,
                "directive_id": str(directive_id) if directive_id else None,
            },
        )

        return GitCreateBranchResponse(
            provider=link.provider,
            branch_name=branch_name,
            commit_sha=branch_info.commit_sha,
            directive_id=directive_id,
        )

    def create_branch_for_directive(
        self,
        *,
        directive_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        directive_title: str = "",
        from_sha: str | None = None,
    ) -> tuple[bool, str | None, str | None, str | None]:
        """Create a git branch for a directive after it has been issued.

        Returns (created: bool, branch_name, commit_sha, warning_message).
        This method NEVER raises — failures are returned as (False, None, None, warning).
        The caller (directive issue endpoint) remains authoritative on state.
        """
        link = self._get_repo_link(project_id)
        if link is None:
            return False, None, None, None  # no repo linked — not an error

        branch_name = directive_branch_name(directive_id, directive_title)
        if not validate_trident_branch_name(branch_name):
            return False, None, None, f"invalid_branch_name:{branch_name}"

        # Resolve SHA
        proj = self._get_project(project_id)
        resolved_sha = from_sha or proj.git_commit_sha
        if not resolved_sha:
            try:
                resolved_sha = self._provider.get_default_branch_sha(
                    owner=link.owner, repo_name=link.repo_name
                )
            except GitProviderError as e:
                warning = f"git_sha_unavailable:{e.reason_code}"
                self._audit.record(
                    event_type=AuditEventType.GIT_BRANCH_CREATE_FAILED,
                    event_payload={
                        "directive_id": str(directive_id),
                        "project_id": str(project_id),
                        "reason_code": "sha_unavailable",
                        "provider_error_code": e.reason_code,
                    },
                    actor_type=AuditActorType.SYSTEM,
                    actor_id="trident-directive-issue",
                    project_id=project_id,
                )
                return False, None, None, warning

        try:
            branch_info = self._provider.create_branch(
                owner=link.owner,
                repo_name=link.repo_name,
                branch_name=branch_name,
                from_sha=resolved_sha,
            )
        except GitProviderError as e:
            warning = f"git_branch_create_failed:{e.reason_code}"
            self._audit.record(
                event_type=AuditEventType.GIT_BRANCH_CREATE_FAILED,
                event_payload={
                    "directive_id": str(directive_id),
                    "project_id": str(project_id),
                    "branch_name": branch_name,
                    "reason_code": "provider_error",
                    "provider_error_code": e.reason_code,
                },
                actor_type=AuditActorType.SYSTEM,
                actor_id="trident-directive-issue",
                project_id=project_id,
            )
            return False, branch_name, None, warning

        # Persist log
        log_row = GitBranchLog(
            project_id=project_id,
            directive_id=directive_id,
            provider=link.provider,
            branch_name=branch_name,
            commit_sha=branch_info.commit_sha,
            commit_message=None,
            created_by_user_id=user_id,
            event_type="branch_created",
        )
        self._db.add(log_row)
        self._db.flush()

        # Success audit
        self._audit.record(
            event_type=AuditEventType.GIT_BRANCH_CREATED,
            event_payload={
                "provider": link.provider,
                "owner": link.owner,
                "repo_name": link.repo_name,
                "branch_name": branch_name,
                "commit_sha": branch_info.commit_sha,
                "directive_id": str(directive_id),
            },
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            project_id=project_id,
        )

        return True, branch_name, branch_info.commit_sha, None

    def push_files_for_directive(
        self,
        project_id: uuid.UUID,
        directive_id: uuid.UUID,
        user_id: uuid.UUID,
        body: GitPushFilesRequest,
    ) -> GitPushFilesResponse:
        link = self._require_repo_link(project_id)
        proj = self._get_project(project_id)

        # Validate directive belongs to project
        directive = self._db.get(Directive, directive_id)
        if directive is None or directive.project_id != project_id:
            raise GitDirectiveMismatchError("directive_not_in_project")

        # Validate file paths
        path_err = _validate_file_paths(body.files)
        if path_err:
            raise GitInvalidBranchNameError(path_err)  # reuse error class — semantics are path safety

        # Resolve branch from GitBranchLog (latest branch_created for this directive)
        log_row = self._db.scalars(
            select(GitBranchLog)
            .where(
                GitBranchLog.project_id == project_id,
                GitBranchLog.directive_id == directive_id,
                GitBranchLog.event_type == "branch_created",
            )
            .order_by(GitBranchLog.created_at.desc())
            .limit(1)
        ).first()
        if log_row is None:
            raise GitNotLinkedError("directive_branch_missing")

        branch_name = log_row.branch_name
        files_dict = {f.path: f.content for f in body.files}

        commit_info = self._provider.push_files(
            owner=link.owner,
            repo_name=link.repo_name,
            branch_name=branch_name,
            files=files_dict,
            message=body.commit_message,
        )

        # Persist commit log
        commit_log = GitBranchLog(
            project_id=project_id,
            directive_id=directive_id,
            provider=link.provider,
            branch_name=branch_name,
            commit_sha=commit_info.sha,
            commit_message=body.commit_message,
            created_by_user_id=user_id,
            event_type="commit_pushed",
        )
        self._db.add(commit_log)

        # Update project HEAD SHA
        proj.git_commit_sha = commit_info.sha
        self._db.flush()

        # Proof object (ProofObject requires directive_id non-null)
        proof_id: uuid.UUID | None = None
        try:
            proof = ProofObject(
                directive_id=directive_id,
                proof_type="GIT_COMMIT_PUSHED",
                proof_uri=commit_info.html_url,
                proof_summary=(
                    f"provider={link.provider} owner={link.owner} repo={link.repo_name} "
                    f"branch={branch_name} sha={commit_info.sha} files={len(body.files)}"
                ),
                proof_hash=commit_info.sha,
                created_by_agent_role="USER",
            )
            self._db.add(proof)
            self._db.flush()
            proof_id = proof.id
        except Exception:
            pass  # proof is non-blocking

        # Audit — no file contents
        self._audit.record(
            event_type=AuditEventType.GIT_COMMIT_PUSHED,
            event_payload={
                "provider": link.provider,
                "owner": link.owner,
                "repo_name": link.repo_name,
                "branch_name": branch_name,
                "commit_sha": commit_info.sha,
                "commit_message": body.commit_message,
                "file_count": len(body.files),
                "directive_id": str(directive_id),
                "proof_object_id": str(proof_id) if proof_id else None,
            },
            actor_type=AuditActorType.USER,
            actor_id=str(user_id),
            project_id=project_id,
        )

        return GitPushFilesResponse(
            provider=link.provider,
            owner=link.owner,
            repo_name=link.repo_name,
            branch_name=branch_name,
            commit_sha=commit_info.sha,
            commit_message=body.commit_message,
            file_count=len(body.files),
            proof_object_id=proof_id,
        )

    def list_branches(self, project_id: uuid.UUID) -> GitBranchListResponse:
        rows = list(self._db.scalars(
            select(GitBranchLog)
            .where(GitBranchLog.project_id == project_id)
            .order_by(GitBranchLog.created_at.desc())
        ).all())
        return GitBranchListResponse(
            items=[
                GitBranchResponse(
                    provider=r.provider,
                    branch_name=r.branch_name,
                    commit_sha=r.commit_sha,
                    directive_id=r.directive_id,
                    event_type=r.event_type,
                    created_at=r.created_at,
                )
                for r in rows
            ]
        )
