# Directive workflow log (engineering ↔ architect)

**Note:** Program mandate Apr 2026: authoritative unified log is **`WORKFLOW_LOG.md`** (same folder). This table remains a compact engineering↔architect receipt; extend **`WORKFLOW_LOG.md`** for gates and formal audit.

**Purpose:** Single append-only record so reviewers can validate the chain:

**Directive issued → work performed → proof returned → architect accept/reject → (if accepted) permanent log entry.**

**Rules**

1. Engineering adds or updates the **Proof returned** section when handing back artifacts (commit SHAs, migrations, test commands, clawbot outputs as summarized).
2. The **architect** records **Decision** as `ACCEPTED` or `REJECTED`, with name/date and any conditions.
3. Do **not** delete or rewrite past rows; add a new row if proof is re-run after rejection.
4. If rejected, add a short **Follow-up** note and link the replacement row when exists.

---

## Canonical naming standard (effective 2026-05-01)

All future directives use `TRIDENT_<DOMAIN>_<SEQUENCE>`. Historical `TRIDENT_IMPLEMENTATION_DIRECTIVE_*` names are retained as aliases. Canonical registry: **`trident/docs/TRIDENT_DIRECTIVE_REGISTRY.md`**.

---

## Log entries (newest first)

> **Alias column added 2026-05-01** — `TRIDENT_REGISTRY_CLEANUP_001` backfill.

| ID | Directive | Canonical alias | Phase | Proof summary (engineering) | Architect decision | Logged |
|----|-----------|----------------|-------|------------------------------|--------------------|--------|
| W-056 | **TRIDENT_DIRECTIVE_REGISTRY_CLEANUP_001** | `TRIDENT_REGISTRY_CLEANUP_001` | Docs — registry backfill | `TRIDENT_DIRECTIVE_REGISTRY.md` created; `DIRECTIVE_WORKFLOW_LOG.md` + `WORKFLOW_LOG.md` + manifest updated with canonical aliases; naming standard established. | **ACCEPTED** | 2026-05-01 |
| W-055 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_VSCODE_001** | `TRIDENT_VSCODE_001` | VS Code extension | `getExecutionState()` + `ExecutionStateResponse` TS interfaces; `executionStatePanel.ts` (WebView, 9 action buttons from backend); `trident.showExecutionState` command; TS compile ✓ | **ACCEPTED** | 2026-05-01 |
| W-054 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_STATUS_001** (final) | `TRIDENT_STATUS_001` | Execution-state aggregate | `ExecutionStateService`, `ExecutionStateResponse` (9 actions with reason_code + blocking_reasons with required_next_action); `GET /execution-state`; DB-only, zero provider calls; **21 tests** | **ACCEPTED** | 2026-05-01 |
| W-053 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_STATUS_001** (iteration 1) | `TRIDENT_STATUS_001` (v1) | Status aggregate | `DirectiveStateService`, `GET /status`; lifecycle_phase, git/patch/validation/signoff + allowed_actions; **20 tests** | **ACCEPTED** | 2026-05-01 |
| W-052 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_SIGNOFF_001** | `TRIDENT_SIGNOFF_001` | Sign-off + closure | `DirectiveStatus.CLOSED`, `signoff001001` migration, `SignoffService` (PASSED ≥ 1, FAILED = 0), `/signoff` endpoint, `DIRECTIVE_SIGNOFF` proof, post-closure 409 guards; **14 tests** | **ACCEPTED** | 2026-05-01 |
| W-051 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_VALIDATION_001** | `TRIDENT_VALIDATION_001` | Validation tracking | `valid001001` migration, `ValidationRun` ORM, PENDING→RUNNING→PASSED→FAILED→WAIVED, `/validations` CRUD + start/complete/waive, proof on terminal; **26 tests** | **ACCEPTED** | 2026-05-01 |
| W-050 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_PATCH_002** | `TRIDENT_PATCH_002` | Patch execution | `patch002001` migration, `PatchExecutionStatus`, `/patches/{id}/execute`, `_convert_files_changed`, duplicate guard, retry, `PATCH_EXECUTED/FAILED` audit; **17 tests** | **ACCEPTED** | 2026-05-01 |
| W-049 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_PATCH_001** | `TRIDENT_PATCH_001` | Patch proposals | `patch001001` migration, `PatchProposal` ORM, PROPOSED→ACCEPTED→REJECTED→SUPERSEDED, immutability, `/patches` CRUD + accept/reject, proof on accept; **20 tests** | **ACCEPTED** | 2026-05-01 |
| W-048 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_005** | `TRIDENT_GITHUB_005` | Git push files | `push_files_for_directive()`, `/push-files` endpoint, path validation, `GitBranchLog(commit_pushed)`, `GIT_COMMIT_PUSHED` proof, `Project.git_commit_sha` update; **16 tests** | **ACCEPTED** | 2026-05-01 |
| W-047 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_004** | `TRIDENT_GITHUB_004` | Directive branch binding | `get_optional_git_provider`, `DirectiveIssueResponse` + git fields (additive), `create_branch_for_directive`, `GIT_BRANCH_CREATE_FAILED` audit; **10 tests** | **ACCEPTED** | 2026-05-01 |
| W-046 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_003** | `TRIDENT_GITHUB_003` | GitHub API endpoints | `GitProjectService`, `/create-repo`, `/link-repo`, `/repo-status`, `/create-branch`, `/branches`; RBAC; no token leakage; **23 tests** | **ACCEPTED** | 2026-05-01 |
| W-045 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_002** | `TRIDENT_GITHUB_002` | Git schema | `github002001` migration, `git_repo_links`, `git_branch_log`, `ProofObjectType.GIT_BRANCH_CREATED/PUSHED`, 4 new AuditEventTypes; **16 tests** | **ACCEPTED** | 2026-05-01 |
| W-044 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_GITHUB_001** | `TRIDENT_GITHUB_001` | GitHub provider | `GitProvider` ABC, `GitHubProvider`, `GitHubClient` (sole token holder), registry (fail-closed), `directive_branch_name`; **29 tests** | **ACCEPTED** | 2026-05-01 |
| W-043 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_ONBOARD_002** | `TRIDENT_ONBOARD_002` | Onboarding scan service | `OnboardingScanService` (11 checks, secrets count-only, path safety), `/onboarding` begin/scan/scan-result/status; **28 tests** | **ACCEPTED** | 2026-05-01 |
| W-042 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_ONBOARD_001** | `TRIDENT_ONBOARD_001` | Onboarding schema | `onboard001001` migration, `ProjectOnboarding` ORM, `OnboardingStatus` × 8, `ONBOARDING_AUDIT` gate, 5 audit events; **15 tests** | **ACCEPTED** | 2026-05-01 |
| W-041 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_MODEL_ROUTER_002** | `TRIDENT_MODEL_ROUTER_002` | Model plane wiring (EXTERNAL branch) | `ModelPlaneRouterService` wired into `ModelRouterService.route` EXTERNAL only; dual audit; `MODEL_PLANE_UNAVAILABLE` block; **144 tests** | **ACCEPTED** | 2026-05-01 |
| W-040 | **TRIDENT_VALIDATION_DIRECTIVE_001** | `TRIDENT_VALIDATION_DIRECTIVE_001` | Live end-to-end validation | SSH to both hosts; 8/8 scenarios PASS (primary, secondary guard, fail-closed, circuit breaker, timeout, no-bypass, status endpoint) | **ACCEPTED** | 2026-05-01 |
| W-039 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_MODEL_ROUTER_001** | `TRIDENT_MODEL_ROUTER_001` | Model plane wiring | `ModelPlaneRouterService`, probes, circuit breaker, `model_plane_wiring_v1` audit, `/model-plane-status`; **139 tests** | **ACCEPTED** | 2026-05-01 |
| W-038 | **TRIDENT_IMPLEMENTATION_DIRECTIVE_001** | `TRIDENT_IMPL_001` | Control plane foundation | `impl001001` migration, JWT auth, projects, membership, OWNER/ADMIN/CONTRIBUTOR/VIEWER, directives DRAFT→ISSUED, StateTransitionService; **130 tests** | **ACCEPTED** | 2026-04-30 |
| W-037 | **STATE_001** | `TRIDENT_STATE_001` (legacy) | Schema foundation | **`state001001`** migration + `StateTransitionLog` / `ProjectGate` ORM + additive **`DirectiveStatus`** / **`TaskLifecycleState`** + **`GateStatus`**; **`STATE_001_PLAN.md`**. | **ISSUED** — **STATE_001_PLAN `READY`** | 2026-04-30 |
| W-036 | **APP_LLD_001** | LLD — epics + directives | **`APP_LLD_001.md`** **ACCEPTED** program **2026-04-30**; manifest + logs aligned. | **ACCEPTED** | 2026-04-30 |
| W-035 | **DOC_APP_BLUEPRINT_ALIGNMENT** | Docs — manifest + guides | **`APP_BLUEPRINT_001`** in **`TRIDENT_DOCUMENT_MANIFEST_v1_0.md`**; Master Guide **§2.1**; **`WORKFLOW_LOG.md`** ACCEPT rows; **`APP_LLD_001_PLAN.md`** placeholder. **No code.** | **ACCEPTED** — **LLD-only** build-planning unblock | 2026-04-30 |
| W-034 | **APP_BLUEPRINT_001** | Product blueprint acceptance | Canonical **`trident/docs/APP_BLUEPRINT_001.md`** + addenda (Workbench UI/workflow, shared thread, RAG, model cadre, project structure, prerequisites, environment governance, state engine). | **ACCEPTED AS PRODUCT BLUEPRINT** | 2026-04-30 |
| W-033 | **APP_BLUEPRINT_PREREQUISITES_ADDENDUM** | Blueprint return | Prerequisites / environment readiness gate; logged **ACCEPTED** in **`WORKFLOW_LOG.md`**. | **ACCEPTED** | 2026-04-30 |
| W-032 | **APP_BLUEPRINT_STATE_ENGINE_ADDENDUM** | Blueprint return | State engine enforcement design; logged **ACCEPTED** in **`WORKFLOW_LOG.md`**. | **ACCEPTED** | 2026-04-30 |
| W-031 | **FIX_003** | Phase 2 — Read + Plan | Step 1 Read + Step 2 Plan: heartbeat **`last_heartbeat_at`**, new statuses, **`POST /locks/heartbeat`**, stale lazy transition, recovery/takeover/force-release, audits, IDE/web visibility, tests. **`FIX_003_PLAN` `READY`**. Log: **`WORKFLOW_LOG.md`** §FIX_003. **Commit:** **`d9be1bf`**. | **PENDING** — ACK **`FIX_003_PLAN`** | 2026-04-30 |
| W-030 | **100M** | Gate — architect ACK block | Architect **ACCEPT** engineering block; **`100M`** **`BLOCKED_CONFIRMED`**. **Commit:** **`a0b89de`**. | **BLOCKED_CONFIRMED** — superseded by **FIX_003** issuance (**Option A**) | 2026-04-30 |
| W-029 | **100M** | Phase 2 — Read + Plan | **Step 1 Read** + **Step 2 Plan:** **`100M`** vs **`simulated-mutation`**; **FIX 003** gate. **Commits:** **`695babc`**, **`19ac3be`**. | Superseded by **W-030** confirmation | 2026-04-30 |
| W-028 | **100P** / **100P_FINAL** | Step 3 → ACCEPT | **`GET /api/v1/locks/active`** + TTL + IDE governance; **`pytest` 83**. **Commits:** **`565b6ae`**, **`c162fca`**. | **ACCEPTED** — **CLOSED** | 2026-04-30 |
| W-027 | **100P** | Phase 2 — Read + Plan | Plan delivered; **`100P_PLAN` ACCEPTED**. **Commits:** **`7ff7a7d`**, **`b35df98`**. | Superseded by **W-028** | 2026-04-30 |
| W-026 | **100K** / **100K_FINAL** | Step 3 → ACCEPT | **`POST /api/v1/ide/chat`** stub + **`IDE_CHAT_*`** + **`CHAT_LOG`**; extension; **`pytest` 79**. **Commits:** **`dc5e2dc`**, **`08195af`**. | **ACCEPTED** — **CLOSED** | 2026-04-30 |
| W-025 | **100K** | Phase 2 — Read + Plan | **Step 1 Read** + **Step 2 Plan** delivered. **Commit:** **`59af1a2`** (+ **`e52a420`** SHA note). | Superseded by **W-026** | 2026-04-30 |
| W-024 | **100U** / **100U_FINAL** | Step 3 Build → clawbot CONFIRM | **Web UI:** Vite React SPA; nginx proxy; **`getApiBase`** fix **`34ba2a1`**; clawbot **`docker compose build trident-web`** + **`up`**; **`GET /`** + **`/trident/api/health`** PASS; PNG proofs in **`docs/proof_100u_clawbot/`**. **Commits:** **`806e2c3`**, **`34ba2a1`**, proof **`e224996`**. | **ACCEPTED** — **PASS_CONFIRMED** | 2026-04-30 |
| W-023 | **100L** / **100L_FINAL** | Step 3 Build → ACCEPT | **Production hardening:** compose **`restart: unless-stopped`** + **`cpus`/`mem_limit`**; worker/exec **`depends_on` api `service_healthy`**; **`logging_utils`** caps chromadb/httpx/httpcore at INFO; **`trident/docs/OPERATIONS_RUNBOOK.md`**; **`pytest` 77 passed**. **Commits:** **`26ef506`**, **`88ecbdb`**. Clawbot re-run **optional** (non-blocking). | **ACCEPTED** | 2026-04-30 |
| W-022 | **100J_FINAL** | Clawbot gate | **100J** deployment validation: full stack **`down`** → **`build --no-cache`** → **`up`**; Postgres **`audit_events`/`memory_entries`** **215 / 25** unchanged; **Alembic** **`100e001 (head)`**; **`clawbot_100i_proof.py`** primary **PASS** + **`docker compose restart trident-api`** verify **PASS** (**`100i_clawbot_proof_ok=1`**, **`100i_clawbot_proof_verify_ok=1`**, **`restart_verify_PASS=1`**); verify directive **`31e10b91-d605-4d8f-a19c-97c0db3a2366`**; **`EXECUTION_LOG`** **`d84af3d4-8f01-49b8-a98a-9e9b2c7bab8e`**; **`/trident/api/health`** confirmed; **`WORKFLOW_LOG.md`** §100J_FINAL commit **`2dd6d15`**; clawbot pull **HEAD** **`3c31e6c`**. | **ACCEPTED** | 2026-04-30 |
| W-021 | **100I_FINAL** | Clawbot gate | **`clawbot_100i_proof.py`** primary + restart verify on clawbot; **`100i_clawbot_proof_ok=1`**, **`100i_clawbot_proof_verify_ok=1`**, **`restart_verify_PASS=1`**; **`EXECUTION_LOG`** proof; **`agent:engineer`** memory; audit chain + MCP bypass **PASS**; directive **`COMPLETE`** / ledger **`CLOSED`**. **HEAD:** **`c6378e0`** · **Verify directive:** **`7ef53f28-c5fe-4804-bb6c-61c517eebdb1`**. | **ACCEPTED** | 2026-04-30 |
| W-020 | **100I** | Step 3 Build | Harness **`clawbot_100i_proof.py`** + Dockerfile + **`tests/test_clawbot_100i_proof.py`**; **`WORKFLOW_LOG.md`** RUN ORDER §100I. Router→workflow→agent/MCP/memory/audit/proof + restart verify env **`TRIDENT_100I_VERIFY_DIRECTIVE_ID`**. **Commit:** **`428ee04`** (+ subsequent **`c6378e0`** acceptance bundle). | **ACCEPTED** (superseded by **W-021** clawbot PASS) | 2026-04-30 |
| W-019 | **100I** | Gate — Step 3 Build | Program **`DOC_MODEL_CADRE_INTEGRATION = PASS`**; **100I UNBLOCKED**. **Step 3 — Build authorized.** Proof on **clawbot** (Postgres + compose); scope Router→LangGraph→Agent→MCP→Memory→Audit→Proof→final state; **no** 100R / UI / agent-behavior expansion. See **`WORKFLOW_LOG.md`** §100I Step 3 Build AUTHORIZED. | **AUTHORIZED** | 2026-04-30 |
| W-018 | **DOC_MODEL_CADRE_INTEGRATION** | Docs | **Model cadre** integrated: **SINGLE_MODEL_MODE** / **CADRE_MODE**; per-role profiles; **32GB** local-first target; external **fallback only**; provisional candidates in **000G**; **100I** scope clarified (no LLM routing; non-blocking check only); **100R** owns implementation. Files: Manifest, Master Guide v1.1, **000G**, **100R**, **100H**, **100I**, **`WORKFLOW_LOG.md`** §DOC_MODEL_CADRE_INTEGRATION. **Commit:** **`508c109`**. | **ACCEPTED** — **100I** gate lifted | 2026-04-30 |
| W-017 | **100H_FINAL** | Clawbot gate | **CONDITIONAL PASS** — local/unit proof complete; **final acceptance** requires **`clawbot_100h_proof.py`** on deployed stack (Postgres audits + MCP receipt + `agent:engineer` memory + vector state + **restart** `TRIDENT_100H_VERIFY_DIRECTIVE_ID`); see **`WORKFLOW_LOG.md`** §100H_FINAL. | **PENDING** program ACCEPT | 2026-04-30 |
| W-016 | **100H** — Agent execution layer | Step 3 Build | **`app/agents/`** + spine engineer hook; **`AGENT_*`** audits + **`MCPService`** + **`MemoryWriter`**; **`tests/test_agents_100h.py`**; full suite **`pytest` 72 passed**. **Commit:** git log subject **`feat(100H): agent execution layer — LangGraph engineer hook, MCP, audits`** | **PENDING** program ACCEPT on **100H_FINAL** (incl. clawbot) | 2026-04-30 |
| W-015 | **DOC_100H_CONFLICT_RESOLUTION** | Program gate | Program **ACCEPT** — conflict resolved; **100H** = Backend Agent Execution Layer; **100U** = Web UI; **100H Step 3 Build** authorized. Recorded commit **`60df87f`**. | **ACCEPTED** | 2026-04-30 |
| W-014 | **DOC_100H_CONFLICT_RESOLUTION** | Docs | UI directive **`100H_UI` → `100U`** (`TRIDENT_IMPLEMENTATION_DIRECTIVE_100U_UI.md`); new **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100H_AGENT_EXECUTION_LAYER.md`** (backend agents only); Manifest / Master Guides / Playbooks / **100G–100K** / **000P** / **000O** / **FIX 006** / **`WORKFLOW_LOG`** updated. Proof: single docs-only merge on **`main`** (message contains **DOC_100H_CONFLICT_RESOLUTION**). | **PENDING** program ACCEPT | 2026-04-30 |
| W-005 | **100E** — Git + File Lock | Final | **Commits:** implementation `c70c7ce`; clawbot bundle `4482f2c` (API image: `git` + `clawbot_100e_proof.py`). **Alembic:** `100e001` (head). **Clawbot:** `docker compose` rebuild; `alembic upgrade head`; Postgres proof script: acquire lock → conflict OK → release → re-acquire → simulated mutation → `ProofObject(GIT_DIFF)`; audits `GIT_STATUS_CHECKED` / `DIFF_GENERATED`; **restart `trident-api`** → ACTIVE lock row still in Postgres; **pytest** `tests/test_locks_100e.py` **8 passed** in container. **Non-blocking:** orphan `trident-vector`. | **ACCEPTED** — proof list: HEAD `4482f2c`, Alembic `100e001`, lock/conflict/release/restart/read-only git/simulated mutation/proofs/audits/container tests all PASS (per architect sign-off 2026-04-30). | 2026-04-30 |
| W-004 | **FIX 004** — Memory consistency / transaction model | Plan → Final | **Plan:** sequencing **100D → FIX 004 → 100E** acknowledged. **Commits:** `679cba9` (implementation); `592ef30` (API image includes tests for `compose exec pytest`); `ae42405` (TestClient ignores deploy `TRIDENT_BASE_PATH=/trident`). **Alembic:** `fix004001`. **Proof:** vector lifecycle + sequence + structured fallback + retry; clawbot PASS (memory suites + migrations); HEAD **`ae42405`** at final clawbot gate before subsequent merges. | **ACCEPTED** (plan + implementation + clawbot proof per thread). | 2026-04-30 |
| W-003 | **100D** — Memory system | Final | **Commit:** `b0113bf` (memory + Chroma integration baseline). **Proof:** Local PersistentClient — **5** `tests/test_memory_100d.py` passed; clawbot Docker Chroma HttpClient — **5** passed; MiniLM download stabilized; compose `trident-chroma`, API `TRIDENT_CHROMA_HOST=trident-chroma`. Environmental failures (interrupted download) treated as non-code, re-run required. | **ACCEPTED** — structured proof PASS local + clawbot; directive closed before FIX 004 gate (per architect messages in thread). | 2026-04-29 / 2026-04-30 |
| W-002 | **100D** | Environmental note | Task/job interrupted during Chroma ONNX fetch; partial cache cleared; re-validation required (not a code failure). | N/A (informational) | 2026-04-29 |
| W-010 | **DOC_100G_CONFLICT_RESOLUTION** | Docs | Legacy LLM router moved to **100R**; **100G** file = subsystem router; Manifest / Master Guide / **000G** / FIX **005** / Playbooks updated. | **PENDING** program ACK on doc bundle | 2026-04-30 |
| W-013 | **100H** — Agent execution layer | Read / Plan | **`WORKFLOW_LOG.md`** §100H; plan **ACCEPTED IN PRINCIPLE**; build **BLOCKED** — **100H UI** vs **100H Agent** directive ID conflict. | **CONDITIONAL** — build blocked until ID resolution | 2026-04-30 |
| W-012 | **100G_FINAL** | Program gate | Program **ACCEPTED** subsystem router + clawbot proof; unlock **100H** issuance. | **ACCEPTED** | 2026-04-30 |
| W-011 | **100G** — Subsystem router | Step 3 Build | **`POST /api/v1/router/route`**; **ROUTER_DECISION_MADE**; pytest + clawbot `100g_clawbot_proof_ok=1`; commits **`1595f05`** / **`efccb69`**. | **ACCEPTED** — clawbot PASS `2026-04-30`. | 2026-04-30 |
| W-009 | **100G** — Router (orchestration) | Read / Plan | Step 1 Read + Step 2 Plan in **`WORKFLOW_LOG.md`**; subsystem routing only (not legacy LLM doc **100G** file); **ROUTER_DECISION_MADE** logging planned. | **PENDING** — plan acceptance before build. | 2026-04-30 |
| W-008 | **100F_FINAL** | Clawbot gate | **`WORKFLOW_LOG.md`** §100F_FINAL execution record. Git `7f3153c`; alembic `100e001`; validation + restart-low PASS on clawbot. | **ACCEPTED** — PASS `2026-04-30`. | 2026-04-30 |
| W-007 | **100F** — MCP execution | Step 3 Build | **`WORKFLOW_LOG.md`** canonical detail. **Commit:** `feat(100F)` merge on main (see git). **Tests:** `tests/test_mcp_100f.py`; **`POST /api/v1/mcp/classify`**, **`POST /api/v1/mcp/execute`**; simulated adapters; HIGH gate + `EXECUTION_LOG` proofs + MCP audits; `clawbot_100f_proof.py`; session fix for 403 commits. | **ACCEPTED** — plan ack + build proof per thread (Step 3). | 2026-04-30 |
| W-001 | **100F** — MCP execution | Read / Plan only | Engineering delivered **Step 1 Read** + **Step 2 Plan** from `TRIDENT_IMPLEMENTATION_DIRECTIVE_100F_MCP_EXECUTION.md`. **No build** until plan acknowledgment. | **PENDING** — await explicit architect acknowledgment of plan; then Step 3 Build. | 2026-04-30 |

---

## Backfill note

Entries **W-003–W-005** reconstruct this thread’s outcomes; timestamps are **best-effort** from chat and clawbot logs. If your records differ (exact acceptance dates or commit SHAs), append a **correction row** rather than editing history.

---

## Template (copy for next directive)

```markdown
### [W-NNN] DIRECTIVE_ID — Title

- **Issued:** YYYY-MM-DD (architect)
- **Engineering work:** (short scope)
- **Proof returned:** (commits, migrations, tests, clawbot command/output summary, artifacts)
- **Architect decision:** ACCEPTED | REJECTED — YYYY-MM-DD — (name optional)
- **Conditions / gaps:** (if any)
```

---

END
