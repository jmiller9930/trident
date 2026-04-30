"""Schema validation — directive 100B §12.1."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models.enums import AgentRole, DirectiveStatus, ProofObjectType, TaskLifecycleState
from app.schemas.directive import CreateDirectiveRequest


def test_valid_directive_request_accepted() -> None:
    body = CreateDirectiveRequest(
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        title="Hello",
        graph_id=None,
        created_by_user_id=uuid.uuid4(),
        status=DirectiveStatus.DRAFT,
    )
    assert body.title == "Hello"


def test_invalid_directive_status_rejected() -> None:
    with pytest.raises(ValidationError):
        CreateDirectiveRequest(
            workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            title="x",
            created_by_user_id=uuid.uuid4(),
            status="NOT_A_STATUS",  # type: ignore[arg-type]
        )


def test_task_state_enum_rejects_bad_value() -> None:
    with pytest.raises(ValueError):
        TaskLifecycleState("INVALID")


def test_agent_role_enum_rejects_bad_value() -> None:
    with pytest.raises(ValueError):
        AgentRole("INVALID_ROLE")


def test_proof_type_enum_rejects_bad_value() -> None:
    with pytest.raises(ValueError):
        ProofObjectType("INVALID_PROOF")
