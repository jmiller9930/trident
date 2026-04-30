"""Nike queue states — directive 100O."""

from enum import StrEnum


class NikeEventStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class NikeAttemptOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    FAILED = "FAILED"


class NikeOutboxStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED_NOT_CONFIGURED = "SKIPPED_NOT_CONFIGURED"


class NikeOutboxChannel(StrEnum):
    INTERNAL = "INTERNAL"
