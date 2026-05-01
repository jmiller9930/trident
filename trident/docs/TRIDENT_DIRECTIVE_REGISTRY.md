# TRIDENT Directive Registry

**Document type:** Canonical directive index  
**Status:** Active  
**Owner:** Chief Architect + Engineering  
**Created:** 2026-05-01  
**Updated:** 2026-05-01

---

## Naming Standard (Effective 2026-05-01)

All future directives must use canonical naming:

```
TRIDENT_<DOMAIN>_<SEQUENCE>
```

**Examples:** `TRIDENT_ONBOARD_001`, `TRIDENT_GITHUB_001`, `TRIDENT_PATCH_001`

Old-style `TRIDENT_IMPLEMENTATION_DIRECTIVE_*` names are **deprecated** but **retained as historical aliases** and must never be erased from logs.

---

## Domain Codes

| Code | Subsystem |
|------|-----------|
| `IMPL` | Control plane / authentication / project foundation |
| `ONBOARD` | Existing project onboarding |
| `GITHUB` | Git provider / GitHub integration |
| `MODEL_ROUTER` | Model plane wiring and routing |
| `PATCH` | Patch proposal and execution |
| `VALIDATION` | Post-commit validation |
| `SIGNOFF` | Directive closure / sign-off |
| `STATUS` | Execution state aggregation |
| `VSCODE` | VS Code extension workbench |
| `REGISTRY` | Documentation and registry |

---

## Directive Registry Table

### Control Plane Foundation

| Canonical | Historical alias | Status | Migration head | Tests | Summary |
|-----------|-----------------|--------|---------------|-------|---------|
| `TRIDENT_IMPL_001` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_001` | **PASS / ACCEPTED** | `impl001001` | 164 passed | JWT auth, projects, membership, OWNER/ADMIN/CONTRIBUTOR/VIEWER RBAC, directives DRAFT→ISSUED, StateTransitionService, audit log |

**Files changed:**
- `app/security/{passwords,jwt_tokens}.py`
- `app/models/{project_member,project_invite}.py`
- `app/api/v1/{auth,projects,members}.py`
- `app/repositories/membership_repository.py`
- `app/services/state_transition_service.py`
- `alembic/versions/impl001001_control_plane.py`
- `tests/test_impl_directive_001.py`

---

### Model Plane Wiring

| Canonical | Historical alias | Status | Config | Tests | Summary |
|-----------|-----------------|--------|--------|-------|---------|
| `TRIDENT_MODEL_ROUTER_001` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_MODEL_ROUTER_001` | **PASS / ACCEPTED** | `TRIDENT_MODEL_ROUTER_BASE_URL` | 139 passed | `ModelPlaneRouterService`, health probes, circuit breaker, primary/secondary endpoint, `MODEL_ROUTING_DECISION (model_plane_wiring_v1)` audit, `/system/model-plane-status` |
| `TRIDENT_MODEL_ROUTER_002` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_MODEL_ROUTER_002` | **PASS / ACCEPTED** | `TRIDENT_ENGINEER_USE_MODEL_PLANE` | 144 passed | Wires `ModelPlaneRouterService` into `ModelRouterService.route` EXTERNAL branch; dual audit (fix005 + model_plane_wiring_v1); fail-closed; `correlation_id` linkage |
| `TRIDENT_VALIDATION_DIRECTIVE_001` | `TRIDENT_VALIDATION_DIRECTIVE_001` | **PASS** | — | 8/8 PASS (live) | Live end-to-end validation: primary Ollama call, secondary guard, primary down fail-closed, circuit breaker, timeout, no-bypass static scan, status endpoint |

**Files changed (MODEL_ROUTER_001):**
- `app/services/model_router.py` (new)
- `app/api/deps/git_deps.py`
- `app/api/v1/system.py` (model-plane-status)
- `tests/test_model_plane_router_001.py`

**Files changed (MODEL_ROUTER_002):**
- `app/model_router/model_router_service.py`
- `app/model_router/reason_codes.py` (`MODEL_PLANE_UNAVAILABLE`)
- `tests/test_model_router_002.py`

---

### Existing Project Onboarding

| Canonical | Historical alias | Status | Migration head | Tests | Summary |
|-----------|-----------------|--------|---------------|-------|---------|
| `TRIDENT_ONBOARD_001` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_ONBOARD_001` | **PASS / ACCEPTED** | `onboard001001` | 15 tests | `project_onboarding` table, `ProjectOnboarding` ORM, `OnboardingStatus` × 8, `ProjectGateType.ONBOARDING_AUDIT`, 5 new audit event types, `Project` nullable columns |
| `TRIDENT_ONBOARD_002` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_ONBOARD_002` | **PASS / ACCEPTED** | _(schema only)_ | 28 tests | `OnboardingScanService` (11 audit checks, secrets count-only, path safety), `/onboarding/begin`, `/scan`, `/scan-result`, `/status` endpoints |

**Files changed (ONBOARD_001):**
- `app/models/project_onboarding.py`
- `app/models/state_enums.py` (OnboardingStatus)
- `alembic/versions/onboard001001_project_onboarding_schema.py`
- `tests/test_onboard_001_schema.py`

**Files changed (ONBOARD_002):**
- `app/services/onboarding_scan_service.py`
- `app/schemas/onboarding_schemas.py`
- `app/api/v1/onboarding.py`
- `tests/test_onboard_002_scan.py`

---

### GitHub Provider

| Canonical | Historical alias | Status | Migration head | Tests | Summary |
|-----------|-----------------|--------|---------------|-------|---------|
| `TRIDENT_GITHUB_001` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_001` | **PASS / ACCEPTED** | — | 29 tests | `GitProvider` ABC, `GitHubProvider`, `GitHubClient` (sole token holder), `git_provider_for_settings`, `directive_branch_name` utility; token isolated |
| `TRIDENT_GITHUB_002` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_002` | **PASS / ACCEPTED** | — | 16 tests | `git_repo_links`, `git_branch_log` tables, `ProofObjectType.GIT_BRANCH_CREATED/PUSHED`, `AuditEventType.GIT_REPO_CREATED/LINKED/BRANCH_CREATED/COMMIT_PUSHED` |
| `TRIDENT_GITHUB_003` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_003` | **PASS / ACCEPTED** | — | 23 tests | `/git/create-repo`, `/link-repo`, `/repo-status`, `/create-branch`, `/branches` endpoints; `GitProjectService`; RBAC; audit; no token leakage |
| `TRIDENT_GITHUB_004` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_004` | **PASS / ACCEPTED** | — | 10 tests | Directive issue → Git branch auto-creation (non-blocking); `DirectiveIssueResponse` + `git_branch_created/name/sha/warning`; `GIT_BRANCH_CREATE_FAILED` audit |
| `TRIDENT_GITHUB_005` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_005` | **PASS / ACCEPTED** | — | 16 tests | `push_files_for_directive()` → `/directives/{id}/push-files`; path validation; `GitBranchLog(commit_pushed)`; `ProofObject(GIT_COMMIT_PUSHED)`; `Project.git_commit_sha` updated |

**Files changed (GITHUB_001):**
- `app/git_provider/{__init__,base,branch_naming,registry}.py`
- `app/git_provider/github/{__init__,github_client,github_provider,github_schemas}.py`
- `tests/test_github_provider_001.py`

**Files changed (GITHUB_002):**
- `app/models/{git_repo_link,git_branch_log}.py`
- `alembic/versions/github002001_git_repo_links_and_branch_log.py`
- `tests/test_github_002_schema.py`

**Files changed (GITHUB_003):**
- `app/schemas/git_schemas.py`
- `app/api/deps/git_deps.py`
- `app/services/git_project_service.py`
- `app/api/v1/git.py`
- `tests/test_github_003_api.py`

**Files changed (GITHUB_004):**
- `app/schemas/directive.py` (DirectiveIssueResponse, additive)
- `app/models/enums.py` (GIT_BRANCH_CREATE_FAILED)
- `app/api/deps/git_deps.py` (get_optional_git_provider)
- `app/api/v1/directives.py` (issue endpoint extended)
- `tests/test_github_004_directive_branch.py`

**Files changed (GITHUB_005):**
- `app/schemas/git_schemas.py` (GitPushFilesRequest/Response)
- `app/services/git_project_service.py` (push_files_for_directive)
- `app/api/v1/git.py` (/directives/{id}/push-files)
- `tests/test_github_005_push_files.py`

---

### Patch Proposal

| Canonical | Historical alias | Status | Migration head | Tests | Summary |
|-----------|-----------------|--------|---------------|-------|---------|
| `TRIDENT_PATCH_001` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_PATCH_001` | **PASS / ACCEPTED** | `patch001001` | 20 tests | `patch_proposals` table, `PatchProposalStatus` PROPOSED→ACCEPTED→REJECTED→SUPERSEDED, immutability enforcement, `/patches` CRUD + accept/reject, `ProofObject` on accept |
| `TRIDENT_PATCH_002` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_PATCH_002` | **PASS / ACCEPTED** | `patch002001` | 17 tests | `PatchExecutionStatus`, execution columns on `patch_proposals`, `/patches/{id}/execute` → `push_files_for_directive`, duplicate guard, retry-on-failure-no-commit, `PATCH_EXECUTED/FAILED` audit |

**Files changed (PATCH_001):**
- `app/models/patch_proposal.py`
- `app/schemas/proposal_schemas.py`
- `app/services/patch_proposal_service.py`
- `app/api/v1/patch_proposals.py`
- `alembic/versions/patch001001_patch_proposals_table.py`
- `tests/test_patch_001.py`

**Files changed (PATCH_002):**
- `app/models/patch_proposal.py` (PatchExecutionStatus + columns)
- `app/schemas/proposal_schemas.py` (PatchExecuteResponse)
- `app/services/patch_proposal_service.py` (execute, _convert_files_changed)
- `app/api/v1/patch_proposals.py` (/execute endpoint)
- `alembic/versions/patch002001_patch_proposal_execution_fields.py`
- `tests/test_patch_002.py`

---

### Validation

| Canonical | Historical alias | Status | Migration head | Tests | Summary |
|-----------|-----------------|--------|---------------|-------|---------|
| `TRIDENT_VALIDATION_001` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_VALIDATION_001` | **PASS / ACCEPTED** | `valid001001` | 26 tests | `validation_runs` table, `ValidationStatus` PENDING→RUNNING→PASSED→FAILED→WAIVED, terminal immutability, `/validations` CRUD + start/complete/waive, proof on PASSED/FAILED |

**Files changed:**
- `app/models/validation_run.py`
- `app/schemas/validation_schemas.py`
- `app/services/validation_run_service.py`
- `app/api/v1/validations.py`
- `alembic/versions/valid001001_validation_runs_table.py`
- `tests/test_validation_001.py`

---

### Sign-Off / Closure

| Canonical | Historical alias | Status | Migration head | Tests | Summary |
|-----------|-----------------|--------|---------------|-------|---------|
| `TRIDENT_SIGNOFF_001` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_SIGNOFF_001` | **PASS / ACCEPTED** | `signoff001001` | 14 tests | `DirectiveStatus.CLOSED`, `closed_at`/`closed_by_user_id` on directives, `SignoffService` (eligibility rules: PASSED ≥ 1 + FAILED = 0), `/directives/{id}/signoff`, `DIRECTIVE_SIGNOFF` proof, post-closure 409 enforcement on patches + validations |

**Files changed:**
- `app/models/{directive,enums}.py`
- `app/schemas/directive.py` (DirectiveSignoffResponse)
- `app/services/signoff_service.py`
- `app/api/v1/directives.py` (/signoff endpoint)
- `app/services/{patch_proposal,validation_run}_service.py` (closure guards)
- `alembic/versions/signoff001001_directive_closure.py`
- `tests/test_signoff_001.py`

---

### Execution State Aggregation

| Canonical | Historical alias | Status | Tests | Summary |
|-----------|-----------------|--------|-------|---------|
| `TRIDENT_STATUS_001` (iteration 1) | `TRIDENT_IMPLEMENTATION_DIRECTIVE_STATUS_001` (prior issue) | **PASS / ACCEPTED** | 20 tests | `GET /directives/{id}/status` — `DirectiveStateResponse` with lifecycle_phase, git, patches, validations, signoff, allowed_actions (VIEWER+) |
| `TRIDENT_STATUS_001` (iteration 2 / final) | `TRIDENT_IMPLEMENTATION_DIRECTIVE_STATUS_001` (final issue) | **PASS / ACCEPTED** | 21 tests | `GET /directives/{id}/execution-state` — `ExecutionStateResponse` with `actions_allowed` (9 actions with `reason_code`/`reason_text`), `blocking_reasons` (with `required_next_action`), DB-only, zero provider calls |

**Files changed:**
- `app/schemas/{directive_state,execution_state_schemas}.py`
- `app/services/{directive_state,execution_state}_service.py`
- `app/api/v1/directive_state.py` (both `/status` and `/execution-state`)
- `tests/{test_status_001,test_execution_state_001}.py`

---

### VS Code Extension

| Canonical | Historical alias | Status | Tests | Summary |
|-----------|-----------------|--------|-------|---------|
| `TRIDENT_VSCODE_001` | `TRIDENT_IMPLEMENTATION_DIRECTIVE_VSCODE_001` | **PASS / ACCEPTED** | TS compile ✓ + manual checklist | `getExecutionState()` in `TridentClient`, `ExecutionStateResponse` TypeScript interfaces, `executionStatePanel.ts` (WebView), `trident.showExecutionState` command, `trident.accessToken` setting; all 9 action buttons state from backend only |

**Files changed:**
- `trident-ide-extension/src/api/tridentClient.ts`
- `trident-ide-extension/src/panels/executionStatePanel.ts` (new)
- `trident-ide-extension/src/extension.ts`
- `trident-ide-extension/package.json`

---

### Registry / Documentation

| Canonical | Historical alias | Status | Summary |
|-----------|-----------------|--------|---------|
| `TRIDENT_REGISTRY_CLEANUP_001` | `TRIDENT_DIRECTIVE_REGISTRY_CLEANUP_001` | **PASS** | This document; canonical naming standard established; registry backfilled; workflow logs updated with aliases |

---

## Current Migration Head

```
signoff001001 (head)
Chain: 100b001 → 100d003 → 100e001 → fix003001 → state001001 → impl001001 → onboard001001 → github002001 → patch001001 → patch002001 → valid001001 → signoff001001
```

## Current Test Suite

**404 passed, 3 skipped** (2026-05-01) — 3 skipped = live validation tests requiring `TRIDENT_VALIDATE_LIVE=1`.

---

## Governing Rules

1. All new directives must use `TRIDENT_<DOMAIN>_<SEQUENCE>` canonical naming.
2. Historical aliases (`TRIDENT_IMPLEMENTATION_DIRECTIVE_*`) are retained and must never be erased.
3. Each directive must record: status, migration head (if applicable), test count, files changed.
4. The migration chain must remain linear and forward-only.
5. No directive may be "reopened" — superseding directives create new entries.
