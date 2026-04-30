"""Memory kinds and collection naming (100D)."""

from enum import StrEnum


class MemoryKind(StrEnum):
    STRUCTURED = "STRUCTURED"
    OBSERVATION = "OBSERVATION"


TRIDENT_MEMORY_COLLECTION = "trident_memory"
