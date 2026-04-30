"""ChromaDB-backed semantic memory (100D). Http server or embedded PersistentClient (no fake HTTP vector)."""

from __future__ import annotations

import logging
import tempfile
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config.settings import Settings
from app.memory.constants import TRIDENT_MEMORY_COLLECTION

logger = logging.getLogger("trident.memory.vector")

# Single-process embedded store when neither remote host nor explicit path is set (pytest / dev without Docker).
_singleton_embed_path: str | None = None


def _embedded_default_path() -> str:
    global _singleton_embed_path
    if _singleton_embed_path is None:
        _singleton_embed_path = tempfile.mkdtemp(prefix="trident-chroma-embed-")
        logger.info("event=chroma_embed_path path=%s", _singleton_embed_path)
    return _singleton_embed_path


def _build_client(cfg: Settings):
    telem = ChromaSettings(anonymized_telemetry=False)
    host = (cfg.chroma_host or "").strip()
    local = (cfg.chroma_local_path or "").strip()
    if host:
        client = chromadb.HttpClient(host=host, port=cfg.chroma_port, settings=telem)
        logger.info("event=chroma_client mode=http host=%s port=%s", host, cfg.chroma_port)
        return client
    path = local if local else _embedded_default_path()
    client = chromadb.PersistentClient(path=path, settings=telem)
    logger.info("event=chroma_client mode=persistent path=%s", path)
    return client


class VectorMemoryService:
    """Thin Chroma wrapper: one logical collection with metadata filters."""

    def __init__(self, cfg: Settings) -> None:
        self._cfg = cfg
        self._client = _build_client(cfg)

    def collection(self):
        return self._client.get_or_create_collection(
            name=TRIDENT_MEMORY_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_document(
        self,
        *,
        doc_id: str,
        document: str,
        project_id: str,
        directive_id: str,
        memory_kind: str,
    ) -> str:
        coll = self.collection()
        coll.upsert(
            ids=[doc_id],
            documents=[document],
            metadatas=[
                {
                    "project_id": project_id,
                    "directive_id": directive_id,
                    "memory_kind": memory_kind,
                }
            ],
        )
        logger.info(
            "event=memory_vector_upsert doc_id=%s directive_id=%s project_id=%s",
            doc_id,
            directive_id,
            project_id,
        )
        return doc_id

    def query_similar(
        self,
        query_text: str,
        *,
        project_id: str,
        directive_id: str | None,
        top_k: int = 8,
    ) -> dict[str, Any]:
        coll = self.collection()
        n_fetch = min(max(top_k * 6, top_k), 64)
        res = coll.query(query_texts=[query_text], n_results=n_fetch, where={"project_id": project_id})
        ids = list(res.get("ids", [[]])[0] or [])
        docs = list(res.get("documents", [[]])[0] or [])
        dists = list(res.get("distances", [[]])[0] or [])
        metas = list(res.get("metadatas", [[]])[0] or [])
        if directive_id:
            kept_ids: list[str] = []
            kept_docs: list[str] = []
            kept_dists: list[float] = []
            kept_metas: list[Any] = []
            for i, meta in enumerate(metas):
                if meta and meta.get("directive_id") == directive_id:
                    kept_ids.append(ids[i])
                    kept_docs.append(docs[i] if i < len(docs) else "")
                    kept_dists.append(dists[i] if i < len(dists) else 0.0)
                    kept_metas.append(meta)
                    if len(kept_ids) >= top_k:
                        break
            ids, docs, dists, metas = kept_ids, kept_docs, kept_dists, kept_metas
        else:
            ids, docs, dists, metas = ids[:top_k], docs[:top_k], dists[:top_k], metas[:top_k]
        logger.info(
            "event=memory_vector_query project_id=%s directive_id=%s hits=%s",
            project_id,
            directive_id or "",
            len(ids),
        )
        return {"ids": ids, "documents": docs, "distances": dists, "metadatas": metas}
