"""OnboardingIndexService — project context indexing for onboarded repositories (ONBOARD_003).

Chunks source files into a project-scoped Chroma namespace: `project:{project_id}`.

Rules:
- Never indexes files with secret findings.
- Never stores secret values.
- Never uses global namespace.
- Never allows cross-project context.
- Path safety enforced throughout.
"""

from __future__ import annotations

import hashlib
import re
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.memory.vector_service import VectorMemoryService
from app.models.project_onboarding import ProjectOnboarding
from app.models.state_enums import OnboardingStatus

# ── Constants ─────────────────────────────────────────────────────────────────

NAMESPACE_PREFIX = "proj"  # Chroma collection names: alphanumeric + hyphens/underscores only
CHUNK_SIZE = 800          # chars per chunk
CHUNK_OVERLAP = 100       # chars overlap between chunks
MAX_FILE_BYTES = 500_000  # 500 KB per file limit

# File extensions to index (source code + docs + config)
INCLUDE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs",
    ".md", ".yaml", ".yml", ".toml", ".json", ".sh",
}

# Filename prefixes/patterns that are always included regardless of extension
INCLUDE_FILENAME_PATTERNS = [
    re.compile(r"^Dockerfile", re.IGNORECASE),
    re.compile(r"^requirements.*\.txt$", re.IGNORECASE),
    re.compile(r"^pyproject\.toml$", re.IGNORECASE),
    re.compile(r"^package\.json$", re.IGNORECASE),
    re.compile(r"^Makefile$", re.IGNORECASE),
    re.compile(r"^Justfile$", re.IGNORECASE),
    re.compile(r"^go\.mod$", re.IGNORECASE),
    re.compile(r"^Cargo\.toml$", re.IGNORECASE),
]

# Filename patterns that are always excluded
EXCLUDE_FILENAME_PATTERNS = [
    re.compile(r"^\.env", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"\.pfx$", re.IGNORECASE),
    re.compile(r"\.p8$", re.IGNORECASE),
    re.compile(r"\.crt$", re.IGNORECASE),
    re.compile(r"\.der$", re.IGNORECASE),
]

# Directories to always skip
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".env",
    "dist", "build", ".next", "coverage", ".pytest_cache", ".mypy_cache",
}

# Secret scan patterns (same as scan service — double-check before indexing)
_SECRET_PATTERNS = [
    re.compile(r"api[_\-]?key\s*[:=]", re.IGNORECASE),
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    re.compile(r"Authorization\s*:\s*(Bearer|Basic)\s", re.IGNORECASE),
    re.compile(r"aws_secret_access_key\s*[:=]", re.IGNORECASE),
    re.compile(r"PRIVATE_KEY\s*[:=]", re.IGNORECASE),
]

# Language hints by extension
_LANG_HINTS: dict[str, str] = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".go": "go",
    ".java": "java", ".rs": "rust", ".md": "markdown",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".json": "json", ".sh": "shell",
}


# ── Result ────────────────────────────────────────────────────────────────────

class IndexJobResult:
    def __init__(
        self,
        success: bool,
        file_count: int = 0,
        chunk_count: int = 0,
        error_safe: str | None = None,
    ) -> None:
        self.success = success
        self.file_count = file_count
        self.chunk_count = chunk_count
        self.error_safe = error_safe


class OnboardingIndexError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:8192]
        return b"\x00" in chunk
    except OSError:
        return True


def _should_include(path: Path) -> bool:
    name = path.name
    # Always exclude
    for pat in EXCLUDE_FILENAME_PATTERNS:
        if pat.search(name):
            return False
    # Always include by name pattern
    for pat in INCLUDE_FILENAME_PATTERNS:
        if pat.search(name):
            return True
    # Include by extension
    return path.suffix.lower() in INCLUDE_EXTENSIONS


def _has_secret(text: str) -> bool:
    for line in text.splitlines():
        if any(p.search(line) for p in _SECRET_PATTERNS):
            return True
    return False


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _chunk_text(text: str, file_path: str) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def _walk_indexable(root: Path) -> list[Path]:
    results: list[Path] = []
    for dirpath, dirnames, filenames in __import__("os").walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        dp = Path(dirpath)
        for fname in filenames:
            fp = dp / fname
            if not _should_include(fp):
                continue
            try:
                if stat.S_ISLNK(fp.lstat().st_mode):
                    continue
                if fp.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            results.append(fp)
    return results


# ── Service ───────────────────────────────────────────────────────────────────

class OnboardingIndexService:
    """Index project source files into a project-scoped Chroma namespace."""

    def __init__(self, cfg: Settings) -> None:
        self._cfg = cfg
        self._vector = VectorMemoryService(cfg)

    def namespace(self, project_id: uuid.UUID) -> str:
        # Chroma collection names: alphanumeric, hyphens, underscores only (no colons)
        hex_id = str(project_id).replace("-", "")
        return f"{NAMESPACE_PREFIX}-{hex_id}"

    def _get_or_create_collection(self, project_id: uuid.UUID):
        ns = self.namespace(project_id)
        return self._vector._client.get_or_create_collection(
            name=ns,
            metadata={"hnsw:space": "cosine", "project_id": str(project_id)},
        )

    def run(
        self,
        *,
        db: Session,
        onboarding: ProjectOnboarding,
        project_id: uuid.UUID,
        waive_secrets: bool = False,
    ) -> IndexJobResult:
        """Run the index job synchronously. Updates onboarding status in-place."""

        # ── Pre-flight checks ─────────────────────────────────────────────────
        art = onboarding.scan_artifact_json or {}
        checks = art.get("checks", {})
        secrets_count = checks.get("secrets_scan", {}).get("findings_count", -1)
        if secrets_count > 0 and not waive_secrets:
            raise OnboardingIndexError(f"index_blocked_secrets_found:{secrets_count}")

        repo_path = onboarding.repo_local_path
        if not repo_path:
            raise OnboardingIndexError("index_blocked_no_repo_path")

        root = Path(repo_path)
        if not root.exists() or not root.is_dir():
            onboarding.index_status = "FAILED"
            onboarding.index_error_safe = "index_blocked_path_inaccessible"
            db.flush()
            raise OnboardingIndexError("index_blocked_path_inaccessible")

        # ── Transition to INDEXING ─────────────────────────────────────────────
        job_id = str(uuid.uuid4())[:8]
        onboarding.index_job_id = job_id
        onboarding.status = OnboardingStatus.INDEXING.value
        onboarding.index_status = "INDEXING"
        db.flush()

        git_sha = onboarding.git_commit_sha or ""
        onboarding_id = str(onboarding.id)
        project_id_str = str(project_id)

        # ── Collect and chunk files ────────────────────────────────────────────
        files = _walk_indexable(root)
        collection = self._get_or_create_collection(project_id)

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        file_count = 0

        for fp in files:
            if _is_binary(fp):
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not text.strip():
                continue
            # Safety: re-check for secrets at index time
            if _has_secret(text):
                continue

            try:
                rel = str(fp.relative_to(root))
            except ValueError:
                continue

            lang = _LANG_HINTS.get(fp.suffix.lower(), "text")
            chunks = _chunk_text(text, rel)
            file_count += 1
            for i, chunk in enumerate(chunks):
                c_hash = _content_hash(chunk)
                doc_id = f"{project_id_str}:{rel}:{i}:{c_hash}"
                ids.append(doc_id)
                documents.append(chunk)
                metadatas.append({
                    "project_id": project_id_str,
                    "onboarding_id": onboarding_id,
                    "file_path": rel,
                    "git_commit_sha": git_sha,
                    "chunk_index": i,
                    "language_hint": lang,
                    "content_hash": c_hash,
                })

        if not ids:
            raise OnboardingIndexError("index_blocked_no_indexable_files")

        # ── Batch upsert into Chroma ──────────────────────────────────────────
        BATCH = 100
        for b in range(0, len(ids), BATCH):
            collection.upsert(
                ids=ids[b:b + BATCH],
                documents=documents[b:b + BATCH],
                metadatas=metadatas[b:b + BATCH],
            )

        chunk_count = len(ids)

        # ── Update onboarding record ──────────────────────────────────────────
        onboarding.status = OnboardingStatus.INDEXED.value
        onboarding.index_status = "INDEXED"
        onboarding.indexed_file_count = file_count
        onboarding.indexed_chunk_count = chunk_count
        onboarding.indexed_at = datetime.now(timezone.utc)
        onboarding.index_error_safe = None
        db.flush()

        return IndexJobResult(success=True, file_count=file_count, chunk_count=chunk_count)

    def query_context(
        self,
        *,
        project_id: uuid.UUID,
        query_text: str,
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Query the project context index. Returns safe result list."""
        try:
            collection = self._get_or_create_collection(project_id)
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            docs = results.get("documents", [[]])[0] or []
            metas = results.get("metadatas", [[]])[0] or []
            dists = results.get("distances", [[]])[0] or []
            return [
                {"document": d, "metadata": m, "distance": dist}
                for d, m, dist in zip(docs, metas, dists)
            ]
        except Exception:
            return []
