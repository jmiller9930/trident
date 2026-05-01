"""TRIDENT_UAT_001 — End-to-end operator acceptance test.

Simulates the full 19-step flow:
  login → project → directive → issue → engineer agent →
  reviewer agent → decision → accept → execute → validation →
  signoff → closed → audit verification

GitHub steps are tested without a live PAT (github_enabled=False).
All state transitions, agents, decision engine, and audit events are verified.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.api.deps.git_deps import get_optional_git_provider
from app.git_provider.base import BranchInfo, CommitInfo, GitProvider, RepoInfo
from app.model_router.model_router_service import ModelRouterResult, ModelRouterService
from app.models.audit_event import AuditEvent
from app.models.decision_record import DecisionRecord, DecisionRecommendation
from app.models.directive import Directive
from app.models.enums import AuditEventType, DirectiveStatus
from app.models.patch_proposal import PatchExecutionStatus, PatchProposal, PatchProposalStatus
from app.models.patch_review import PatchReview, ReviewerRecommendation
from app.models.proof_object import ProofObject
from app.models.validation_run import ValidationRun, ValidationStatus

# ── Shared test fixtures / mocks ──────────────────────────────────────────────

UAT_COMMIT_SHA = "uat001cafebabe0000000000000000000000cafe"
UAT_BRANCH_SHA = "uat001branchsha00000000000000000000branch"

VALID_PATCH_JSON = json.dumps({
    "title": "UAT-001: Add request validation",
    "summary": "Adds input validation to the login endpoint for UAT.",
    "files_changed": [
        {
            "path": "app/auth/login.py",
            "change_type": "update",
            "content": "def login(email: str, password: str):\n    if not email or len(password) < 8:\n        raise ValueError('invalid credentials')\n",
        },
        {
            "path": "tests/test_login.py",
            "change_type": "create",
            "content": "def test_login_validation():\n    pass\n",
        },
    ],
    "unified_diff": "--- a/app/auth/login.py\n+++ b/app/auth/login.py\n@@ -1 +1,3 @@\n+def login(email, password):\n+    if not email: raise ValueError()",
})

ACCEPT_REVIEW_JSON = json.dumps({
    "recommendation": "ACCEPT",
    "confidence": 0.92,
    "summary": "UAT Review: Code is clean, validation logic is sound.",
    "findings": [],
})


def _mock_provider() -> MagicMock:
    m = MagicMock(spec=GitProvider)
    m.provider_name = "github"
    m.link_repo.return_value = RepoInfo(
        provider="github", owner="acme-uat", repo_name="uat-repo",
        clone_url="https://github.com/acme-uat/uat-repo.git",
        html_url="https://github.com/acme-uat/uat-repo",
        default_branch="main", private=True, created=False,
    )
    m.get_default_branch_sha.return_value = UAT_BRANCH_SHA
    m.create_branch.return_value = BranchInfo(
        provider="github", branch_name="trident/uat001xx/uat-001-add-request-validation",
        commit_sha=UAT_BRANCH_SHA,
    )
    m.push_files.return_value = CommitInfo(
        provider="github", sha=UAT_COMMIT_SHA,
        message="trident: UAT-001: Add request validation",
        branch_name="trident/uat001xx/uat-001-add-request-validation",
        html_url=f"https://github.com/acme-uat/uat-repo/commit/{UAT_COMMIT_SHA}",
    )
    return m


def _mock_model_result(text: str) -> MagicMock:
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
    m.local_model_profile_id = "uat_profile"
    m.external_model_id = None
    m.optimized_prompt = None
    m.as_trace_dict.return_value = {
        "decision": "LOCAL", "primary_audit_code": "LOCAL_COMPLETED",
        "escalation_trigger_code": None, "blocked_external": False,
        "blocked_reason_code": None, "calibrated_confidence": 0.88,
        "local_adapter_raw_confidence": 0.88, "signal_breakdown": {},
        "token_optimization": {}, "response_preview": text[:200],
        "local_model_profile_id": "uat_profile", "external_model_id": None,
    }
    return m


def _step(n: int, desc: str, response: Any = None) -> None:
    print(f"\n{'='*60}")
    print(f"UAT STEP {n:02d}: {desc}")
    if response is not None:
        if isinstance(response, dict):
            print(json.dumps(response, indent=2, default=str))
        else:
            print(str(response))


# ═══════════════════════════════════════════════════════════════
# FULL UAT FLOW — single test, 19 steps
# ═══════════════════════════════════════════════════════════════

def test_uat_001_full_operator_flow(client, minimal_project_ids, db_session) -> None:
    """UAT-001 — complete governed operator workflow: login→directive→closed."""

    provider = _mock_provider()
    pid = str(minimal_project_ids["project_id"])

    # ── STEP 1: Login ─────────────────────────────────────────────────────────
    login_r = client.post("/api/v1/auth/login", json={
        "email": minimal_project_ids["email"],
        "password": minimal_project_ids["password"],
    })
    assert login_r.status_code == 200, f"STEP 1 FAIL: {login_r.text}"
    tokens = login_r.json()["tokens"]
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = login_r.json()["user"]["id"]
    _step(1, "LOGIN", {"status": login_r.status_code, "user_id": user_id, "token_type": tokens["token_type"]})

    # ── STEP 2: Select project ────────────────────────────────────────────────
    proj_r = client.get(f"/api/v1/projects/{pid}", headers=h)
    assert proj_r.status_code == 200, f"STEP 2 FAIL: {proj_r.text}"
    _step(2, "PROJECT", {"project_id": pid, "name": proj_r.json()["name"]})

    # ── STEP 3: Link GitHub repo (mocked provider) ────────────────────────────
    client.app.dependency_overrides[get_optional_git_provider] = lambda: provider
    from app.api.deps.git_deps import get_git_provider
    client.app.dependency_overrides[get_git_provider] = lambda: provider
    link_r = client.post(f"/api/v1/projects/{pid}/git/link-repo",
                         json={"clone_url": "https://github.com/acme-uat/uat-repo.git"}, headers=h)
    assert link_r.status_code == 201, f"STEP 3 FAIL: {link_r.text}"
    _step(3, "LINK GITHUB REPO (mocked)", {
        "provider": link_r.json()["provider"],
        "owner": link_r.json()["owner"],
        "repo_name": link_r.json()["repo_name"],
        "clone_url": link_r.json()["clone_url"],
    })

    # ── STEP 4: Create directive ──────────────────────────────────────────────
    dir_r = client.post("/api/v1/directives/", json={
        "project_id": pid,
        "title": "UAT-001: Add request validation to login",
    }, headers=h)
    assert dir_r.status_code == 200, f"STEP 4 FAIL: {dir_r.text}"
    directive_id = dir_r.json()["directive"]["id"]
    _step(4, "CREATE DIRECTIVE", {
        "directive_id": directive_id,
        "title": dir_r.json()["directive"]["title"],
        "status": dir_r.json()["directive"]["status"],
    })

    # ── STEP 5: Issue directive ───────────────────────────────────────────────
    issue_r = client.post(f"/api/v1/directives/{directive_id}/issue", headers=h)
    assert issue_r.status_code == 200, f"STEP 5 FAIL: {issue_r.text}"
    _step(5, "ISSUE DIRECTIVE", {
        "status": issue_r.json()["status"],
        "git_branch_created": issue_r.json()["git_branch_created"],
        "git_branch_name": issue_r.json()["git_branch_name"],
        "git_warning": issue_r.json()["git_warning"],
    })

    # ── STEP 6: Confirm branch created ────────────────────────────────────────
    branches_r = client.get(f"/api/v1/projects/{pid}/git/branches", headers=h)
    assert branches_r.status_code == 200, f"STEP 6 FAIL: {branches_r.text}"
    branch_items = branches_r.json()["items"]
    branch_created_items = [b for b in branch_items if b["event_type"] == "branch_created"]
    assert len(branch_created_items) >= 1, "STEP 6 FAIL: no branch_created log"
    branch_name = branch_created_items[0]["branch_name"]
    _step(6, "CONFIRM BRANCH CREATED", {
        "branch_name": branch_name,
        "commit_sha": branch_created_items[0]["commit_sha"],
        "event_type": branch_created_items[0]["event_type"],
    })

    # ── STEP 7: Run Engineer agent ─────────────────────────────────────────────
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(VALID_PATCH_JSON)):
        eng_r = client.post(f"/api/v1/projects/{pid}/directives/{directive_id}/agents/engineer/run",
                            json={}, headers=h)
    assert eng_r.status_code == 201, f"STEP 7 FAIL: {eng_r.text}"
    patch_id = eng_r.json()["patch_id"]
    _step(7, "RUN ENGINEER AGENT", {
        "patch_id": patch_id,
        "title": eng_r.json()["title"],
        "status": eng_r.json()["status"],
        "model_decision": eng_r.json()["model_routing_trace"]["decision"],
    })

    # ── STEP 8: Confirm patch proposal ────────────────────────────────────────
    patch_r = client.get(f"/api/v1/projects/{pid}/directives/{directive_id}/patches/{patch_id}", headers=h)
    assert patch_r.status_code == 200, f"STEP 8 FAIL: {patch_r.text}"
    assert patch_r.json()["status"] == PatchProposalStatus.PROPOSED.value, "STEP 8 FAIL: patch not PROPOSED"
    _step(8, "CONFIRM PATCH PROPOSAL", {
        "patch_id": patch_id,
        "status": patch_r.json()["status"],
        "proposed_by_agent_role": patch_r.json()["proposed_by_agent_role"],
        "title": patch_r.json()["title"],
    })

    # ── STEP 9: Run Reviewer agent ────────────────────────────────────────────
    with patch.object(ModelRouterService, "route", return_value=_mock_model_result(ACCEPT_REVIEW_JSON)):
        rev_r = client.post(
            f"/api/v1/projects/{pid}/directives/{directive_id}/patches/{patch_id}/agents/reviewer/run",
            json={}, headers=h,
        )
    assert rev_r.status_code == 201, f"STEP 9 FAIL: {rev_r.text}"
    review_id = rev_r.json()["review_id"]
    _step(9, "RUN REVIEWER AGENT", {
        "review_id": review_id,
        "recommendation": rev_r.json()["recommendation"],
        "confidence": rev_r.json()["confidence"],
        "summary": rev_r.json()["summary"],
    })

    # ── STEP 10: Confirm review recorded ─────────────────────────────────────
    assert rev_r.json()["recommendation"] == ReviewerRecommendation.ACCEPT.value
    assert rev_r.json()["confidence"] >= 0.75
    db_session.expire_all()
    review_row = db_session.get(PatchReview, uuid.UUID(review_id))
    assert review_row is not None, "STEP 10 FAIL: PatchReview not persisted"
    _step(10, "CONFIRM REVIEW RECORDED", {
        "review_id": review_id,
        "db_recommendation": review_row.recommendation,
        "db_confidence": review_row.confidence,
        "patch_status_unchanged": db_session.get(PatchProposal, uuid.UUID(patch_id)).status,
    })

    # ── STEP 11: Decision card (GET /decision) ────────────────────────────────
    dec_r = client.get(f"/api/v1/projects/{pid}/directives/{directive_id}/decision?patch_id={patch_id}", headers=h)
    assert dec_r.status_code == 200, f"STEP 11 FAIL: {dec_r.text}"
    assert dec_r.json()["recommendation"] == DecisionRecommendation.ACCEPT_PATCH.value
    _step(11, "DECISION CARD — GET /decision (no persistence)", {
        "recommendation": dec_r.json()["recommendation"],
        "confidence": dec_r.json()["confidence"],
        "summary": dec_r.json()["summary"],
        "recommended_next_api_action": dec_r.json()["recommended_next_api_action"],
        "evidence_count": len(dec_r.json()["evidence"]),
        "persisted": False,
    })

    # ── POST /decision/record (persist to audit) ──────────────────────────────
    rec_r = client.post(
        f"/api/v1/projects/{pid}/directives/{directive_id}/decision/record?patch_id={patch_id}",
        headers=h,
    )
    assert rec_r.status_code == 201, f"STEP 11b FAIL: {rec_r.text}"
    decision_record_id = rec_r.json()["decision_record_id"]
    _step(11, "DECISION RECORD — POST /decision/record", {
        "decision_record_id": decision_record_id,
        "recommendation": rec_r.json()["recommendation"],
        "persisted": rec_r.json()["persisted"],
    })

    # ── STEP 12: Accept patch ─────────────────────────────────────────────────
    acc_r = client.post(f"/api/v1/projects/{pid}/directives/{directive_id}/patches/{patch_id}/accept", headers=h)
    assert acc_r.status_code == 200, f"STEP 12 FAIL: {acc_r.text}"
    assert acc_r.json()["status"] == PatchProposalStatus.ACCEPTED.value
    _step(12, "ACCEPT PATCH", {
        "patch_id": patch_id,
        "status": acc_r.json()["status"],
        "accepted_by_user_id": acc_r.json()["accepted_by_user_id"],
        "proof_object_id": acc_r.json()["proof_object_id"],
    })

    # ── STEP 13: Execute patch ────────────────────────────────────────────────
    exec_r = client.post(
        f"/api/v1/projects/{pid}/directives/{directive_id}/patches/{patch_id}/execute",
        headers=h,
    )
    assert exec_r.status_code == 201, f"STEP 13 FAIL: {exec_r.text}"
    assert exec_r.json()["commit_sha"] == UAT_COMMIT_SHA
    exec_proof_id = exec_r.json()["proof_object_id"]
    _step(13, "EXECUTE PATCH", {
        "commit_sha": exec_r.json()["commit_sha"],
        "branch_name": exec_r.json()["branch_name"],
        "proof_object_id": exec_proof_id,
        "execution_status": "EXECUTED",
    })

    # ── STEP 14: Confirm commit SHA + proof ───────────────────────────────────
    db_session.expire_all()
    patch_row = db_session.get(PatchProposal, uuid.UUID(patch_id))
    assert patch_row.execution_commit_sha == UAT_COMMIT_SHA, "STEP 14 FAIL: commit SHA mismatch"
    proof_row = db_session.get(ProofObject, uuid.UUID(exec_proof_id))
    assert proof_row is not None, "STEP 14 FAIL: no proof object"
    _step(14, "CONFIRM COMMIT SHA + PROOF", {
        "commit_sha": patch_row.execution_commit_sha,
        "execution_branch": patch_row.execution_branch_name,
        "proof_type": proof_row.proof_type,
        "proof_hash": proof_row.proof_hash,
    })

    # ── STEP 15: Create validation ────────────────────────────────────────────
    val_r = client.post(
        f"/api/v1/projects/{pid}/directives/{directive_id}/validations",
        json={
            "validation_type": "MANUAL",
            "commit_sha": UAT_COMMIT_SHA,
        },
        headers=h,
    )
    assert val_r.status_code == 201, f"STEP 15 FAIL: {val_r.text}"
    validation_id = val_r.json()["id"]
    _step(15, "CREATE VALIDATION", {
        "validation_id": validation_id,
        "status": val_r.json()["status"],
        "validation_type": val_r.json()["validation_type"],
        "commit_sha": val_r.json()["commit_sha"],
    })

    # ── STEP 16: Mark validation PASSED ──────────────────────────────────────
    pass_r = client.post(
        f"/api/v1/projects/{pid}/directives/{directive_id}/validations/{validation_id}/complete",
        json={"passed": True, "result_summary": "UAT-001: All manual checks passed. Login validation confirmed working."},
        headers=h,
    )
    assert pass_r.status_code == 200, f"STEP 16 FAIL: {pass_r.text}"
    assert pass_r.json()["status"] == ValidationStatus.PASSED.value
    val_proof_id = pass_r.json()["proof_object_id"]
    _step(16, "MARK VALIDATION PASSED", {
        "validation_id": validation_id,
        "status": pass_r.json()["status"],
        "completed_by_user_id": pass_r.json()["completed_by_user_id"],
        "proof_object_id": val_proof_id,
    })

    # ── STEP 17: Signoff directive ────────────────────────────────────────────
    signoff_r = client.post(f"/api/v1/directives/{directive_id}/signoff", headers=h)
    assert signoff_r.status_code == 200, f"STEP 17 FAIL: {signoff_r.text}"
    assert signoff_r.json()["status"] == DirectiveStatus.CLOSED.value
    signoff_proof_id = signoff_r.json()["proof_object_id"]
    _step(17, "SIGNOFF DIRECTIVE", {
        "directive_id": directive_id,
        "status": signoff_r.json()["status"],
        "closed_at": signoff_r.json()["closed_at"],
        "closed_by_user_id": signoff_r.json()["closed_by_user_id"],
        "proof_object_id": signoff_proof_id,
    })

    # ── STEP 18: Confirm CLOSED ───────────────────────────────────────────────
    db_session.expire_all()
    d = db_session.get(Directive, uuid.UUID(directive_id))
    assert d.status == DirectiveStatus.CLOSED.value, "STEP 18 FAIL: directive not CLOSED"
    assert d.closed_at is not None
    _step(18, "CONFIRM DIRECTIVE CLOSED", {
        "directive_id": directive_id,
        "status": d.status,
        "closed_at": str(d.closed_at),
        "closed_by_user_id": str(d.closed_by_user_id),
    })

    # ── STEP 19: Execution-state closed state ─────────────────────────────────
    es_r = client.get(f"/api/v1/projects/{pid}/directives/{directive_id}/execution-state", headers=h)
    assert es_r.status_code == 200, f"STEP 19 FAIL: {es_r.text}"
    es = es_r.json()
    assert es["signoff"]["closed"] is True, "STEP 19 FAIL: closed not reflected"
    aa = es["actions_allowed"]
    mutating = ["create_patch","accept_patch","reject_patch","execute_patch",
                "create_validation","start_validation","complete_validation","waive_validation","signoff"]
    blocked_actions = [k for k in mutating if aa[k]["allowed"] is False]
    assert len(blocked_actions) == len(mutating), f"STEP 19 FAIL: some mutation actions still enabled: {set(mutating)-set(blocked_actions)}"
    _step(19, "EXECUTION-STATE PANEL — CLOSED (all mutations disabled)", {
        "signoff.closed": es["signoff"]["closed"],
        "proof_object_id": es["signoff"]["proof_object_id"],
        "all_mutation_actions_disabled": len(blocked_actions) == len(mutating),
        "disabled_actions": blocked_actions,
        "blocking_reasons_count": len(es["blocking_reasons"]),
    })

    # ── AUDIT VERIFICATION ────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("AUDIT VERIFICATION")

    audit_checks = [
        (AuditEventType.AGENT_RUN_COMPLETED, "AGENT_RUN_COMPLETED"),
        (AuditEventType.AGENT_REVIEW_COMPLETED, "AGENT_REVIEW_COMPLETED"),
        (AuditEventType.DECISION_RECORDED, "DECISION_RECORDED"),
        (AuditEventType.PATCH_ACCEPTED, "PATCH_ACCEPTED"),
        (AuditEventType.PATCH_EXECUTED, "PATCH_EXECUTED"),
        (AuditEventType.VALIDATION_PASSED, "VALIDATION_PASSED"),
        (AuditEventType.SIGNOFF_COMPLETED, "SIGNOFF_COMPLETED"),
    ]
    audit_proof: dict[str, Any] = {}
    for event_type, label in audit_checks:
        row = db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == event_type.value,
                AuditEvent.directive_id == uuid.UUID(directive_id),
            )
        ).first()
        assert row is not None, f"AUDIT FAIL: missing {label}"
        payload = row.event_payload_json
        # Verify no file content in audit
        payload_str = json.dumps(payload)
        assert "def login" not in payload_str, f"AUDIT FAIL: file content in {label}"
        audit_proof[label] = {
            "event_id": str(row.id),
            "event_type": row.event_type,
            "actor_id": row.actor_id,
            "key_fields": {k: v for k, v in payload.items() if k not in ("signal_breakdown",)},
        }
        print(f"  ✓ {label}: {row.id}")

    _step(99, "AUDIT EVENTS VERIFIED", audit_proof)

    # ── GitHub proof (mocked) ─────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("GITHUB PROOF (mocked — live requires TRIDENT_GITHUB_ENABLED=true + PAT)")
    print(f"  Provider:    github")
    print(f"  Owner:       acme-uat")
    print(f"  Repo:        uat-repo")
    print(f"  Branch:      {branch_name}")
    print(f"  Commit SHA:  {UAT_COMMIT_SHA}")
    print(f"  Clone URL:   https://github.com/acme-uat/uat-repo.git")
    print(f"  Note: Real GitHub writes require TRIDENT_GITHUB_ENABLED=true + valid PAT on deployment")

    client.app.dependency_overrides.clear()

    print(f"\n{'='*60}")
    print("UAT-001 RESULT: PASS")
    print("All 19 steps completed. All 7 required audit events verified. No file content in audit payloads.")
