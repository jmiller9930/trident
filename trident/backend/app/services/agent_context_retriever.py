"""AgentContextRetriever — project-scoped RAG context injection (TRIDENT_AGENT_CONTEXT_001).

Queries the project Chroma namespace and formats context blocks for agent prompts.
Fails gracefully when index is not available — agents fall back to current behavior.

Rules:
- Only accesses namespace proj-{project_id_hex} — no cross-project access
- Does not store or log raw chunk content (only file counts in audit)
- Truncates context to token budget before prompt injection
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.config.settings import Settings

# ── Config ────────────────────────────────────────────────────────────────────

CONTEXT_TOP_K = 8          # chunks to retrieve
CONTEXT_MAX_CHARS = 3000   # hard cap on injected context (token safety)
CHUNK_PREVIEW_CHARS = 350  # max chars shown per chunk in prompt
MAX_FILES_IN_CONTEXT = 6   # deduplicate to at most this many files


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class RetrievedContext:
    chunks: list[dict[str, Any]] = field(default_factory=list)
    context_used: bool = False
    chunk_count: int = 0
    files_used: int = 0
    warning: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.chunks


# ── Service ───────────────────────────────────────────────────────────────────

class AgentContextRetriever:
    """Query the project context index and format for agent prompt injection."""

    def __init__(self, cfg: Settings) -> None:
        self._cfg = cfg

    def _namespace(self, project_id: uuid.UUID) -> str:
        return f"proj-{str(project_id).replace('-', '')}"

    def retrieve(
        self,
        project_id: uuid.UUID,
        query_text: str,
        n_results: int = CONTEXT_TOP_K,
    ) -> RetrievedContext:
        """Query the project index. Returns empty context on any failure — never raises."""
        from app.services.onboarding_index_service import OnboardingIndexService

        svc = OnboardingIndexService(self._cfg)
        try:
            chunks = svc.query_context(
                project_id=project_id,
                query_text=query_text,
                n_results=n_results,
            )
        except Exception as e:
            return RetrievedContext(warning=f"context_retrieval_error:{type(e).__name__}")

        if not chunks:
            return RetrievedContext(warning="no_context_chunks_found")

        # Deduplicate by file_path (keep highest-scoring chunk per file)
        seen_paths: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            meta = chunk.get("metadata") or {}
            path = meta.get("file_path", "unknown")
            if path not in seen_paths:
                seen_paths[path] = chunk
            if len(seen_paths) >= MAX_FILES_IN_CONTEXT:
                break

        unique_chunks = list(seen_paths.values())
        return RetrievedContext(
            chunks=unique_chunks,
            context_used=True,
            chunk_count=len(chunks),
            files_used=len(unique_chunks),
        )

    def format_context_block(self, ctx: RetrievedContext) -> str:
        """Format retrieved chunks into a [PROJECT CONTEXT] block for prompt injection."""
        if ctx.is_empty:
            return ""

        lines = ["[PROJECT CONTEXT]"]
        total_chars = 0

        for chunk in ctx.chunks:
            meta = chunk.get("metadata") or {}
            doc = str(chunk.get("document", ""))
            file_path = meta.get("file_path", "unknown")
            lang = meta.get("language_hint", "text")

            snippet = doc[:CHUNK_PREVIEW_CHARS]
            if len(doc) > CHUNK_PREVIEW_CHARS:
                snippet += "\n  ...(truncated)"

            block = (
                f"\nFile: {file_path}\n"
                f"Language: {lang}\n"
                f"Snippet:\n{snippet}"
            )
            if total_chars + len(block) > CONTEXT_MAX_CHARS:
                lines.append("\n  ...(context truncated to fit token budget)")
                break
            lines.append(block)
            total_chars += len(block)

        return "\n".join(lines)
