"""State-engine enums (STATE_001) — blueprint-aligned lifecycle vocabulary."""

from enum import StrEnum


class GateStatus(StrEnum):
    """Project gate checklist status (prerequisite / environment gate)."""

    READY = "READY"
    MISSING = "MISSING"
    DEGRADED = "DEGRADED"
    WAIVED = "WAIVED"
    BLOCKING = "BLOCKING"


class ProjectGateType(StrEnum):
    PLAN = "PLAN"
    STRUCTURE = "STRUCTURE"
    PREREQS = "PREREQS"
    ONBOARDING_AUDIT = "ONBOARDING_AUDIT"


class OnboardingStatus(StrEnum):
    PENDING = "PENDING"
    SCANNING = "SCANNING"
    SCANNED = "SCANNED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class StateTransitionActorType(StrEnum):
    """Actor recorded on state_transition_log rows."""

    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
