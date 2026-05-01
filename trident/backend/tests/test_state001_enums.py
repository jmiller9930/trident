"""STATE_001 — additive enums and gate types."""

from app.models.enums import DirectiveStatus, TaskLifecycleState
from app.models.state_enums import GateStatus, ProjectGateType, StateTransitionActorType


def test_directive_status_additive_blueprint_values():
    assert DirectiveStatus.ISSUED.value == "ISSUED"
    assert DirectiveStatus.PROOF_ACCEPTED.value == "PROOF_ACCEPTED"
    assert DirectiveStatus.BLOCKED.value == "BLOCKED"
    # legacy
    assert DirectiveStatus.COMPLETE.value == "COMPLETE"


def test_task_lifecycle_additive():
    assert TaskLifecycleState.PROOF_RETURNED.value == "PROOF_RETURNED"
    assert TaskLifecycleState.BUG_CHECKING.value == "BUG_CHECKING"


def test_gate_status_values():
    assert set(GateStatus) >= {GateStatus.READY, GateStatus.BLOCKING, GateStatus.WAIVED}


def test_project_gate_type_values():
    assert ProjectGateType.PLAN.value == "PLAN"
    assert ProjectGateType.PREREQS.value == "PREREQS"


def test_transition_actor_type():
    assert StateTransitionActorType.AGENT.value == "AGENT"
