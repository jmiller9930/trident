"""TRIDENT_AGENT_CONTEXT_001 — project RAG context wired into Engineer + Reviewer agents."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.api.deps.git_deps import get_git_provider, get_optional_git_provider
from app.git_provider.base import BranchInfo, CommitInfo, GitProvider, RepoInfo
from app.model_router.model_router_service import ModelRouterResult, ModelRouterService
from app.models.audit_event import AuditEvent
from app.models.enums import AuditEventType
from app.models.patch_proposal import PatchProposal, PatchProposalStatus
from app.models.patch_review import PatchReview
from app.repositories.directive_repository import DirectiveRepository
from app.schemas.directive import CreateDirectiveRequest
from app.services.agent_context_retriever import (
    CONTEXT_MAX_CHARS,
    AgentContextRetriever,
    RetrievedContext,
)
from app.services.onboarding_index_service import OnboardingIndexService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login(client, ids) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"email": ids["email"], "password": ids["password"]})
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


def _pid(ids) -> str:
    return str(ids["project_id"])


def _make_directive_and_issue(client, db_session, ids) -> tuple[uuid.UUID, dict]:
    h = _login(client, ids)
    body = CreateDirectiveRequest(
        workspace_id=ids["workspace_id"],
        project_id=ids["project_id"],
        title="Add input validation to run_case",
        created_by_user_id=ids["user_id"],
    )
    d, _, _ = DirectiveRepository(db_session).create_directive_and_initialize(body)
    db_session.commit()
    client.post(f"/api/v1/directives/{d.id}/issue", headers=h)
    db_session.expire_all()
    return d.id, h


def _mock_model(text: str) -> MagicMock:
    m = MagicMock(spec=ModelRouterResult)
    m.decision = "LOCAL"
    m.response_text = text
    m.primary_audit_code = "LOCAL_COMPLETED"
    m.escalation_trigger_code = None
    m.blocked_external = False
    m.blocked_reason_code = None
    m.calibrated_confidence = 0.88
    m.local_adapter_raw_confidence = 0.88
    m.signal_breakdown = {}
    m.token_optimization = {}
    m.local_model_profile_id = "test_profile"
    m.external_model_id = None
    m.optimized_prompt = None
    m.as_trace_dict.return_value = {
        "decision": "LOCAL", "primary_audit_code": "LOCAL_COMPLETED",
        "escalation_trigger_code": None, "blocked_external": False,
        "blocked_reason_code": None, "calibrated_confidence": 0.88,
        "local_adapter_raw_confidence": 0.88, "signal_breakdown": {},
        "token_optimization": {}, "response_preview": text[:200],
        "local_model_profile_id": "test_profile", "external_model_id": None,
    }
    return m


VALID_PATCH = json.dumps({
    "title": "Add validation",
    "summary": "Adds input checks",
    "files_changed": [{"path": "app/main.py", "change_type": "update",
                       "content": "def main():\n    pass\n"}],
    "unified_diff": "",
})

ACCEPT_REVIEW = json.dumps({
    "recommendation": "ACCEPT",
    "confidence": 0.90,
    "summary": "Looks good",
    "findings": [],
})


def _build_index(ids, tmp_path: Path, cfg) -> None:
    """Index a small repo for the project."""
    from app.config.settings import Settings
    from app.models.project_onboarding import ProjectOnboarding
    from app.models.state_enums import OnboardingStatus
    from tests.conftest import fresh_db as _  # noqa

    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text(
        "class LifecycleEngine:\n    def run_case(self, case_id, symbol, candles):\n        pass\n"
    )
    (root / "utils.py").write_text("def helper(): return True\n")

    # Use the actual index service with the test settings
    svc = OnboardingIndexService(cfg)
    row = MagicMock(spec=ProjectOnboarding)
    row.id = uuid.uuid4()
    row.repo_local_path = str(root)
    row.git_commit_sha = "testsha"
    row.scan_artifact_json = {"checks": {"secrets_scan": {"findings_count": 0}}}
    row.status = OnboardingStatus.SCANNED.value
    row.index_status = "NOT_STARTED"
    row.index_job_id = None

    from sqlalchemy.orm import Session
    mock_db = MagicMock(spec=Session)
    mock_db.flush = MagicMock()

    svc.run(db=mock_db, onboarding=row, project_id=ids["project_id"])
    return svc


# ── AgentContextRetriever unit tests ──────────────────────────────────────────

def test_retriever_returns_empty_context_on_missing_index() -> None:
    from app.config.settings import Settings
    retriever = AgentContextRetriever(Settings(chroma_host="", chroma_local_path=""))
    pid = uuid.uuid4()
    ctx = retriever.retrieve(project_id=pid, query_text="add validation")
    assert not ctx.context_used
    assert ctx.chunk_count == 0
    assert ctx.files_used == 0


def test_format_context_block_empty_returns_empty_string() -> None:
    from app.config.settings import Settings
    retriever = AgentContextRetriever(Settings(chroma_host="", chroma_local_path=""))
    ctx = RetrievedContext()
    assert retriever.format_context_block(ctx) == ""


def test_format_context_block_contains_project_context_header() -> None:
    from app.config.settings import Settings
    retriever = AgentContextRetriever(Settings(chroma_host="", chroma_local_path=""))
    ctx = RetrievedContext(
        chunks=[{"document": "def hello(): pass", "metadata": {"file_path": "main.py", "language_hint": "python"}}],
        context_used=True,
        chunk_count=1,
        files_used=1,
    )
    block = retriever.format_context_block(ctx)
    assert "[PROJECT CONTEXT]" in block
    assert "main.py" in block
    assert "def hello" in block


def test_context_block_bounded_by_max_chars() -> None:
    from app.config.settings import Settings
    retriever = AgentContextRetriever(Settings(chroma_host="", chroma_local_path=""))
    # Create many chunks that would exceed the limit
    chunks = [
        {"document": "x" * 400, "metadata": {"file_path": f"file{i}.py", "language_hint": "python"}}
        for i in range(20)
    ]
    ctx = RetrievedContext(chunks=chunks, context_used=True, chunk_count=20, files_used=20)
    block = retriever.format_context_block(ctx)
    assert len(block) <= CONTEXT_MAX_CHARS + 200  # small buffer for header/truncation marker


def test_namespace_format() -> None:
    from app.config.settings import Settings
    retriever = AgentContextRetriever(Settings(chroma_host="", chroma_local_path=""))
    pid = uuid.uuid4()
    ns = retriever._namespace(pid)
    assert ns.startswith("proj-")
    assert str(pid).replace("-", "") in ns


# ── Prompt injection tests ─────────────────────────────────────────────────────

def test_engineer_prompt_contains_context_block_when_provided() -> None:
    from app.services.agent_runtime_service import _build_engineer_prompt
    from app.models.directive import Directive

    d = MagicMock(spec=Directive)
    d.id = uuid.uuid4()
    d.title = "Test directive"
    ctx_block = "[PROJECT CONTEXT]\nFile: main.py\nSnippet:\ndef hello(): pass"
    prompt = _build_engineer_prompt(d, instruction="add validation", context_block=ctx_block)
    assert "[PROJECT CONTEXT]" in prompt
    assert "main.py" in prompt
    assert "[DIRECTIVE]" in prompt
    assert "[INSTRUCTION]" in prompt


def test_engineer_prompt_no_context_block_when_none() -> None:
    from app.services.agent_runtime_service import _build_engineer_prompt
    from app.models.directive import Directive

    d = MagicMock(spec=Directive)
    d.id = uuid.uuid4()
    d.title = "Test directive"
    prompt = _build_engineer_prompt(d, instruction="add validation", context_block=None)
    # Without a context block, the raw [PROJECT CONTEXT] header should not appear as a section
    # (it may appear in the rules text but not as a top-level block)
    assert "File: " not in prompt or "Snippet:" not in prompt


def test_reviewer_prompt_contains_context_block_when_provided() -> None:
    from app.services.reviewer_runtime_service import _build_reviewer_prompt
    from app.models.directive import Directive
    from app.models.patch_proposal import PatchProposal

    d = MagicMock(spec=Directive)
    d.id = uuid.uuid4()
    d.title = "Test"
    p = MagicMock(spec=PatchProposal)
    p.id = uuid.uuid4()
    p.title = "Fix it"
    p.summary = "Summary"
    p.files_changed = None
    ctx_block = "[PROJECT CONTEXT]\nFile: engine.py\nSnippet:\nclass Engine: pass"
    prompt = _build_reviewer_prompt(d, p, instruction=None, context_block=ctx_block)
    assert "[PROJECT CONTEXT]" in prompt
    assert "engine.py" in prompt
    assert "[PATCH UNDER REVIEW]" in prompt


# ── API-level: context_used in audit ─────────────────────────────────────────

def test_engineer_audit_context_used_false_when_no_index(client, minimal_project_ids, db_session) -> None:
    did, h = _make_directive_and_issue(client, db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    with patch.object(ModelRouterService, "route", return_value=_mock_model(VALID_PATCH)):
        client.post(f"/api/v1/projects/{pid}/directives/{did}/agents/engineer/run",
                    json={}, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.AGENT_RUN_COMPLETED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert "context_used" in p
    assert p["context_used"] is False


def test_engineer_audit_no_raw_context_in_payload(client, minimal_project_ids, db_session) -> None:
    did, h = _make_directive_and_issue(client, db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    with patch.object(ModelRouterService, "route", return_value=_mock_model(VALID_PATCH)):
        client.post(f"/api/v1/projects/{pid}/directives/{did}/agents/engineer/run",
                    json={}, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.AGENT_RUN_COMPLETED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    # Audit must not contain raw code content — only counts
    payload_str = json.dumps(p)
    assert "def hello" not in payload_str
    assert "class LifecycleEngine" not in payload_str
    assert "context_chunk_count" in p
    assert "context_files_used" in p


def test_reviewer_audit_contains_context_fields(client, minimal_project_ids, db_session) -> None:
    did, h = _make_directive_and_issue(client, db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    with patch.object(ModelRouterService, "route", return_value=_mock_model(VALID_PATCH)):
        ep = client.post(f"/api/v1/projects/{pid}/directives/{did}/agents/engineer/run",
                         json={}, headers=h)
    patch_id = ep.json()["patch_id"]
    with patch.object(ModelRouterService, "route", return_value=_mock_model(ACCEPT_REVIEW)):
        client.post(f"/api/v1/projects/{pid}/directives/{did}/patches/{patch_id}/agents/reviewer/run",
                    json={}, headers=h)
    db_session.expire_all()
    row = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == AuditEventType.AGENT_REVIEW_COMPLETED.value)
    ).first()
    assert row is not None
    p = row.event_payload_json
    assert "context_used" in p
    assert "context_chunk_count" in p
    assert "context_files_used" in p


def test_context_fallback_when_no_index_does_not_block_engineer(client, minimal_project_ids, db_session) -> None:
    """No index → context_used=False but agent still runs normally."""
    did, h = _make_directive_and_issue(client, db_session, minimal_project_ids)
    pid = _pid(minimal_project_ids)
    with patch.object(ModelRouterService, "route", return_value=_mock_model(VALID_PATCH)):
        r = client.post(f"/api/v1/projects/{pid}/directives/{did}/agents/engineer/run",
                        json={}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == PatchProposalStatus.PROPOSED.value


def test_context_retriever_with_real_indexed_content(minimal_project_ids: dict, tmp_path: Path) -> None:
    """End-to-end: index real content, then query it and verify retrieval."""
    from app.config.settings import Settings
    from app.services.onboarding_index_service import OnboardingIndexService
    from app.models.project_onboarding import ProjectOnboarding
    from app.models.state_enums import OnboardingStatus

    cfg = Settings(chroma_host="", chroma_local_path="")
    root = tmp_path / "repo"
    root.mkdir()
    (root / "lifecycle_engine.py").write_text(
        "class LifecycleEngine:\n    def run_case(self, case_id: str, symbol: str, candles: list):\n        pass\n"
    )
    (root / "utils.py").write_text("def compute_rsi(prices): pass\n")

    svc = OnboardingIndexService(cfg)
    from unittest.mock import MagicMock
    from sqlalchemy.orm import Session
    mock_db = MagicMock(spec=Session)
    mock_db.flush = MagicMock()
    row = MagicMock(spec=ProjectOnboarding)
    row.id = uuid.uuid4()
    row.repo_local_path = str(root)
    row.git_commit_sha = "sha_context_test"
    row.scan_artifact_json = {"checks": {"secrets_scan": {"findings_count": 0}}}
    row.status = OnboardingStatus.SCANNED.value
    row.index_status = "NOT_STARTED"
    row.index_job_id = None
    svc.run(db=mock_db, onboarding=row, project_id=minimal_project_ids["project_id"])

    retriever = AgentContextRetriever(cfg)
    ctx = retriever.retrieve(
        project_id=minimal_project_ids["project_id"],
        query_text="LifecycleEngine run_case candles",
    )
    # Context should be retrieved
    assert ctx.context_used is True
    assert ctx.chunk_count > 0
    assert ctx.files_used > 0

    # Format block should contain the content
    block = retriever.format_context_block(ctx)
    assert "[PROJECT CONTEXT]" in block
    # Should reference the indexed files
    assert "lifecycle_engine.py" in block or "utils.py" in block
