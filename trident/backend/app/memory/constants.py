"""Memory kinds and collection naming (100D)."""

from enum import StrEnum


class MemoryKind(StrEnum):
    STRUCTURED = "STRUCTURED"
    OBSERVATION = "OBSERVATION"


class MemoryVectorState(StrEnum):
    """Structured row is authoritative; vector sidecar follows these states (FIX 004)."""

    STRUCTURED_COMMITTED = "STRUCTURED_COMMITTED"
    VECTOR_PENDING = "VECTOR_PENDING"
    VECTOR_INDEXED = "VECTOR_INDEXED"
    VECTOR_STALE = "VECTOR_STALE"
    VECTOR_FAILED = "VECTOR_FAILED"


TRIDENT_MEMORY_COLLECTION = "trident_memory"
