"""OnboardingScanService — read-only filesystem audit for existing project onboarding.

Rules (invariant, checked before any file access):
- Never write to the repository.
- Never read outside allowed_root_path.
- Never store secret values — counts only.
- Reject path traversal (../ and symlink escapes).

Scan source:
  If the path is accessible on the server, perform a live scan.
  Otherwise, accept an optional client_manifest dict (pre-built by the VS Code extension).
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any

SCAN_SCHEMA = "onboarding_scan_v1"

# ── Language detection (extension-based heuristic) ────────────────────────────
_EXT_LANG: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".m": "matlab",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".sql": "sql",
    ".tf": "terraform",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".md": "markdown",
}

# ── Framework/tooling heuristic (filename → hint) ────────────────────────────
_FILE_FRAMEWORK: dict[str, str] = {
    "requirements.txt": "python-pip",
    "pyproject.toml": "python-poetry",
    "setup.py": "python-setuptools",
    "Pipfile": "python-pipenv",
    "poetry.lock": "python-poetry",
    "package.json": "node",
    "package-lock.json": "node-npm",
    "yarn.lock": "node-yarn",
    "pnpm-lock.yaml": "node-pnpm",
    "Cargo.toml": "rust-cargo",
    "go.mod": "go",
    "pom.xml": "java-maven",
    "build.gradle": "java-gradle",
    "Gemfile": "ruby-bundler",
    "composer.json": "php-composer",
    "Dockerfile": "docker",
    "docker-compose.yml": "docker-compose",
    "docker-compose.yaml": "docker-compose",
    ".dockerignore": "docker",
    "Makefile": "make",
    "Justfile": "just",
    "tox.ini": "python-tox",
    "pytest.ini": "pytest",
    "jest.config.js": "jest",
    "jest.config.ts": "jest",
    "vitest.config.ts": "vitest",
    "alembic.ini": "alembic",
    "fastapi": "fastapi",
    "manage.py": "django",
    "next.config.js": "nextjs",
    "next.config.ts": "nextjs",
    "vite.config.ts": "vite",
    "tailwind.config.js": "tailwind",
    ".github": "github-actions",
    ".gitlab-ci.yml": "gitlab-ci",
    ".travis.yml": "travis-ci",
}

# ── Secret patterns (regex on file content lines) ────────────────────────────
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"api[_\-]?key\s*[:=]", re.IGNORECASE),
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    re.compile(r"Authorization\s*:\s*(Bearer|Basic)\s", re.IGNORECASE),
    re.compile(r"(access|secret)_?token\s*[:=]", re.IGNORECASE),
    re.compile(r"aws_secret_access_key\s*[:=]", re.IGNORECASE),
    re.compile(r"PRIVATE_KEY\s*[:=]", re.IGNORECASE),
]

# Binary detection: first 8 KB null-byte check
_BINARY_SAMPLE = 8192


class PathTraversalError(ValueError):
    """Raised when a path escapes allowed_root_path."""


def _resolve_safe(candidate: Path, root: Path) -> Path:
    """Return resolved candidate; raise PathTraversalError if outside root."""
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        resolved = candidate
    try:
        resolved.relative_to(root.resolve(strict=False))
    except ValueError as exc:
        raise PathTraversalError(f"path escapes root: {candidate}") from exc
    return resolved


def _is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:_BINARY_SAMPLE]
        return b"\x00" in chunk
    except OSError:
        return True


def _safe_read_text(path: Path, max_bytes: int = 1_000_000) -> str | None:
    try:
        raw = path.read_bytes()[:max_bytes]
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return None


def _walk(root: Path, *, max_files: int = 50_000) -> list[Path]:
    """Walk root, returning all non-hidden regular files (not symlinks escaping root)."""
    result: list[Path] = []
    root_resolved = root.resolve(strict=False)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dp = Path(dirpath)
        # skip hidden dirs
        dirnames[:] = [d for d in dirnames if not d.startswith(".") or d == ".github"]
        for fn in filenames:
            if len(result) >= max_files:
                break
            fp = dp / fn
            try:
                fp_resolved = fp.resolve(strict=False)
                fp_resolved.relative_to(root_resolved)
            except ValueError:
                continue
            try:
                if stat.S_ISLNK(fp.lstat().st_mode):
                    continue
            except OSError:
                continue
            result.append(fp)
    return result


class OnboardingScanService:
    """Perform a read-only audit of an existing repository."""

    def __init__(
        self,
        allowed_root_path: str,
        *,
        client_manifest: dict[str, Any] | None = None,
    ) -> None:
        self._raw_root = allowed_root_path.strip()
        self._client_manifest = client_manifest

    def _root_accessible(self) -> bool:
        p = Path(self._raw_root)
        return p.exists() and p.is_dir()

    def run(
        self,
        *,
        git_commit_sha: str | None = None,
    ) -> dict[str, Any]:
        """Run audit and return scan_artifact_json. Never raises on file errors."""
        root_accessible = self._root_accessible()

        if not root_accessible:
            if self._client_manifest:
                return self._build_from_manifest(git_commit_sha)
            return self._unavailable_result(git_commit_sha)

        root = Path(self._raw_root).resolve(strict=False)

        # Path safety: ensure root doesn't start with / traversal sequences
        if ".." in root.parts:
            return self._unavailable_result(git_commit_sha, reason="traversal_in_root")

        files = _walk(root)
        return self._run_live(root, files, git_commit_sha)

    def _run_live(
        self,
        root: Path,
        files: list[Path],
        git_commit_sha: str | None,
    ) -> dict[str, Any]:
        filenames_lower = {f.name.lower() for f in files}
        filenames_exact = {f.name for f in files}
        rel_names = [str(f.relative_to(root)) for f in files]

        lang_counts: dict[str, int] = {}
        framework_hints: list[str] = []
        dependency_files: list[str] = []
        test_dirs: set[str] = set()
        doc_files: list[str] = []
        env_files: list[str] = []
        has_raw_env = False
        gitignore_content: str | None = None
        secrets_count = 0
        scanned_file_count = 0
        binary_skipped = 0

        for fp in files:
            rel = fp.relative_to(root)
            ext = fp.suffix.lower()
            name = fp.name
            rel_str = str(rel)

            # language
            lang = _EXT_LANG.get(ext)
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

            # framework hints by filename
            hint = _FILE_FRAMEWORK.get(name)
            if hint and hint not in framework_hints:
                framework_hints.append(hint)

            # dependency files
            if name in {
                "requirements.txt", "pyproject.toml", "setup.py", "Pipfile",
                "package.json", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
                "Gemfile", "composer.json",
            }:
                dependency_files.append(rel_str)

            # test dirs
            parts_lower = [p.lower() for p in rel.parts]
            if any(p in ("tests", "test", "spec", "__tests__") for p in parts_lower):
                test_dirs.add(parts_lower[0] if len(parts_lower) > 1 else "tests")

            # docs
            if name.lower() in ("readme.md", "readme.rst", "readme.txt", "changelog.md", "contributing.md", "license"):
                doc_files.append(rel_str)

            # env files
            if name.startswith(".env"):
                env_files.append(rel_str)
                if name == ".env":
                    has_raw_env = True

            # gitignore
            if name == ".gitignore" and str(rel.parent) == ".":
                gitignore_content = _safe_read_text(fp)

            # secrets scan (text files only)
            if _is_binary(fp):
                binary_skipped += 1
                continue
            scanned_file_count += 1

            text = _safe_read_text(fp, max_bytes=512_000)
            if text:
                for line in text.splitlines():
                    if any(p.search(line) for p in _SECRET_PATTERNS):
                        secrets_count += 1

        total_files = len(files)
        # language breakdown percentages
        total_code = sum(lang_counts.values()) or 1
        lang_breakdown = {k: round(v / total_code, 4) for k, v in sorted(lang_counts.items(), key=lambda x: -x[1])}
        primary_lang = max(lang_counts, key=lang_counts.get) if lang_counts else None

        # git check
        git_clean_status = "PASS" if git_commit_sha else "WARN"
        git_clean_detail = f"commit_sha={git_commit_sha}" if git_commit_sha else "no_commit_sha_provided"

        # structure
        try:
            depth = max(len(Path(r).parts) for r in rel_names) if rel_names else 0
        except Exception:
            depth = 0

        # docker
        has_dockerfile = any(n.lower().startswith("dockerfile") for n in filenames_exact)
        compose_files = [r for r in rel_names if Path(r).name.lower() in ("docker-compose.yml", "docker-compose.yaml")]

        # env files / gitignore analysis
        gitignore_ignores_env = False
        gitignore_ignores_secrets = False
        if gitignore_content:
            gi_lower = gitignore_content.lower()
            gitignore_ignores_env = any(p in gi_lower for p in (".env\n", ".env\r", "*.env"))
            gitignore_ignores_secrets = any(p in gi_lower for p in ("*.pem", "*.key", "*.p12", "*.pfx"))

        # test runner hint
        runner_hint: str | None = None
        if "pytest.ini" in filenames_exact or "pytest" in framework_hints or "alembic" in framework_hints:
            runner_hint = "pytest"
        elif any(f in framework_hints for f in ("jest", "vitest")):
            runner_hint = "jest/vitest"

        # gate recommendation
        if secrets_count > 0:
            gate_rec = "BLOCKING"
        elif has_raw_env:
            gate_rec = "MISSING"
        else:
            gate_rec = "READY"

        return {
            "schema": SCAN_SCHEMA,
            "source": "live",
            "git_commit_sha": git_commit_sha,
            "repo_local_path": self._raw_root,
            "total_files_found": total_files,
            "binary_files_skipped": binary_skipped,
            "scanned_text_files": scanned_file_count,
            "checks": {
                "git_clean": {
                    "status": git_clean_status,
                    "detail": git_clean_detail,
                },
                "structure": {
                    "status": "PASS",
                    "detected_root": self._raw_root,
                    "file_count": total_files,
                    "max_depth": depth,
                },
                "languages": {
                    "status": "PASS" if primary_lang else "WARN",
                    "primary": primary_lang,
                    "breakdown": lang_breakdown,
                },
                "frameworks": {
                    "status": "PASS" if framework_hints else "WARN",
                    "hints": framework_hints,
                },
                "dependencies": {
                    "status": "PASS" if dependency_files else "WARN",
                    "files": dependency_files,
                    "count": len(dependency_files),
                },
                "docker_readiness": {
                    "status": "PASS" if has_dockerfile else "WARN",
                    "has_dockerfile": has_dockerfile,
                    "compose_files": compose_files,
                },
                "env_files": {
                    "status": "WARN" if has_raw_env else "PASS",
                    "files": env_files,
                    "has_raw_env": has_raw_env,
                },
                "secrets_scan": {
                    "status": "FAIL" if secrets_count > 0 else "PASS",
                    "findings_count": secrets_count,
                    "patterns_checked": len(_SECRET_PATTERNS),
                },
                "tests": {
                    "status": "PASS" if test_dirs else "WARN",
                    "test_dirs": sorted(test_dirs),
                    "runner_hint": runner_hint,
                },
                "docs": {
                    "status": "PASS" if any("readme" in d.lower() for d in doc_files) else "WARN",
                    "has_readme": any("readme" in d.lower() for d in doc_files),
                    "has_changelog": any("changelog" in d.lower() for d in doc_files),
                },
                "gitignore": {
                    "status": "PASS" if gitignore_content else "WARN",
                    "present": gitignore_content is not None,
                    "ignores_env": gitignore_ignores_env,
                    "ignores_secrets": gitignore_ignores_secrets,
                },
            },
            "gate_recommendation": gate_rec,
            "summary_text": (
                f"{total_files} files scanned; primary language: {primary_lang or 'unknown'}; "
                f"frameworks: {', '.join(framework_hints[:5]) or 'none detected'}; "
                f"secrets findings: {secrets_count}."
            ),
        }

    def _build_from_manifest(self, git_commit_sha: str | None) -> dict[str, Any]:
        """Build scan result from client-provided manifest (when path not locally accessible)."""
        m = self._client_manifest or {}
        return {
            "schema": SCAN_SCHEMA,
            "source": "client_manifest",
            "git_commit_sha": git_commit_sha,
            "repo_local_path": self._raw_root,
            "checks": m.get("checks", {}),
            "gate_recommendation": m.get("gate_recommendation", "MISSING"),
            "summary_text": m.get("summary_text", "Client-provided manifest; server-side scan not available."),
        }

    def _unavailable_result(self, git_commit_sha: str | None, *, reason: str = "path_not_accessible") -> dict[str, Any]:
        return {
            "schema": SCAN_SCHEMA,
            "source": "unavailable",
            "git_commit_sha": git_commit_sha,
            "repo_local_path": self._raw_root,
            "checks": {},
            "gate_recommendation": "MISSING",
            "summary_text": f"Server-side scan unavailable: {reason}. Provide client_manifest to proceed.",
        }
