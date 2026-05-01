"""File lock lifecycle (100E)."""

from enum import StrEnum


class LockStatus(StrEnum):
    ACTIVE = "ACTIVE"
    STALE_PENDING_RECOVERY = "STALE_PENDING_RECOVERY"
    EXPIRED = "EXPIRED"
    RELEASED = "RELEASED"
    FORCE_RELEASED = "FORCE_RELEASED"
    CONFLICTED = "CONFLICTED"
