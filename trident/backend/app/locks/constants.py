"""File lock lifecycle (100E)."""

from enum import StrEnum


class LockStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
