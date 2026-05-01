# APP_LLD_001 — Low-Level Design + Epics

**Directive:** `APP_LLD_001` — Low-Level Design + Epics  
**Status:** **ACCEPTED** — program **2026-04-30**; implementation authorized **only** via issued **`TRIDENT_IMPLEMENTATION_DIRECTIVE_*`** (first wave: **STATE_001**)  
**Parent architecture:** `trident/docs/APP_BLUEPRINT_001.md`  
**Document type:** LLD (executable engineering decomposition — not implementation code)

```yaml
manifest_id: TRIDENT-MANIFEST-v1.0
project: Project Trident
parent_document: TRIDENT_DOCUMENT_MANIFEST_v1_0.md
document_id: APP_LLD_001
document_type: LLD
sequence: POST-BLUEPRINT-v1
status: Accepted
dependencies:
  - trident/docs/APP_BLUEPRINT_001.md
  - APP_BLUEPRINT_STATE_ENGINE_ADDENDUM
  - APP_BLUEPRINT_PREREQUISITES_ADDENDUM
produces:
  - Epic backlog + implementation directive IDs
  - Build order + dependency graph
langgraph_required: true
```

**Rule:** **APP_LLD_001** is **ACCEPTED** (2026-04-30). Each slice requires an issued directive + scoped proof (**STATE_001** first).

---

## 1. Purpose

Decompose **`APP_BLUEPRINT_001`** into **EPICS**, **IMPLEMENTATION DIRECTIVES**, **build order**, and **dependencies**, aligned with:

| Blueprint pillar | Primary epics |
|------------------|----------------|
| State engine | E03 |
| Prerequisite gate | E04 |
| Environment governance | E04 |
| UI / workbench | E01 |
| Shared memory / RAG | E06 |
| Model cadre | E07 |
| Agent system | E02, E07, E08, E09, E10 |
| Patch / lock / apply | E08 |
| Proof / audit / manifest | E09 |

---

## 2. Epic decomposition

### E01 — VS Code Workbench (UI shell)

| Field | Content |
|-------|---------|
| **Description** | Opinionated **three-panel + status bar** layout: left intake + roster; center document workspace; right shared conversation + workflow status; bottom lock/model/directive/warnings. Normal mode hides UUID/raw JSON. |
| **Scope** | Extension-only UX shell + commands + webviews/trees; **all truth from backend aggregates** (no client-side state machine). Debug mode exposes internals. |
| **Dependencies** | **E03** (UI state aggregate API); **E07** (model cadre panel data); **E04** (gate banners). Partial parallel before APIs stubbed with mocks **disallowed for prod path**. |
| **Risks** | Dashboard creep; duplicate state logic in extension; drift vs web UI — mitigate via single API contract. |

---

### E02 — Shared Agent Thread System

| Field | Content |
|-------|---------|
| **Description** | **One team-room thread** per project/directive scope: single chronological feed; agent selector chooses **next responder**; **no context reset** on role switch; role badges on messages. |
| **Scope** | Postgres-backed conversation rows; pagination; correlation with `directive_id` / `project_id`; integration with RAG ingest (`source_type=agent_message`). |
| **Dependencies** | **E06** (retrieval + ingest); **E03** (lifecycle visibility); **E01** (presentation). |
| **Risks** | Accidental per-agent silo tables; prompt stuffing — enforce retrieval pipeline from blueprint. |

---

### E03 — State Engine (enforcement layer)

| Field | Content |
|-------|---------|
| **Description** | **Backend-authoritative** transitions: directive + ledger + **project gates**; **`StateTransitionService`**; invalid transition **409**; **BLOCKED** orthogonal state; audits on every transition. |
| **Scope** | Schema/migrations for gates + optional `directive_phase`; LangGraph/Nike pre-flight; agent pre-mutation checks; UI aggregate endpoint. |
| **Dependencies** | **Foundation:** existing `DirectiveStatus`, `TaskLifecycleState`, audits; **E04** consumes gate evaluation. |
| **Risks** | Dual writers (graph vs API); races on concurrent workflow — transactions + idempotency keys. |

---

### E04 — Prerequisite + Environment Gate

| Field | Content |
|-------|---------|
| **Description** | Unified **checklist** combining **prerequisites** (§ blueprint) and **environment governance** (Dockerfile, compose, `.env.example`, lockfiles); states READY/MISSING/DEGRADED/WAIVED/BLOCKING; **no build if BLOCKING**. |
| **Scope** | CRUD + validate probes + waiver audits; merge with **GateEvaluationService** from state epic; IDE “Environment Readiness” strip. |
| **Dependencies** | **E03** (gate enforcement hooks); **E05** (scaffold/start-build entrypoints). |
| **Risks** | Checkbox theater — bind `validation_type` + audits; waiver abuse — reason + optional secondary approval. |

---

### E05 — Project Type + Structure System

| Field | Content |
|-------|---------|
| **Description** | **Classify project type → architecture → canonical structure → dual approval → scaffold**; scratch mode audited exception. |
| **Scope** | Classifier API + overrides; structure templates per type; artifact versioning in memory; scaffold job idempotency. |
| **Dependencies** | **E03** (PLAN_APPROVED, STRUCTURE_APPROVED gates); **E04** (pre-build gate); **E06** (artifact storage/index). |
| **Risks** | Wrong type propagation; scaffold before approval — server-side hard deny. |

---

### E06 — RAG / Memory System

| Field | Content |
|-------|---------|
| **Description** | **Hybrid** Postgres + vector + keyword/hybrid search; metadata schema per blueprint; shared corpus; stale index detection (`commit_sha`, `vector_state`). |
| **Scope** | Ingest/query APIs; repo indexing; reindex/stale-report; fallback to structured-only degraded mode. |
| **Dependencies** | Existing memory/Chroma path; **100R** for external embed escalation if used. |
| **Risks** | Split-brain local vs lab — lab authoritative; embedding cost. |

---

### E07 — Model Cadre + Routing System

| Field | Content |
|-------|---------|
| **Description** | Per-role model profiles; readiness probe; **Model Cadre Setup** UI; **no silent external** — **100R/FIX005** path only; ties into prerequisite §4. |
| **Scope** | Model cadre APIs from blueprint; integration with **StateTransitionService** for degraded modes; extension + web surfaces. |
| **Dependencies** | **100R** implementation maturity; **E03**, **E04**. |
| **Risks** | Vendor lock-in — configurable registry; drift vs actual inference backends. |

---

### E08 — Patch + Lock + Apply Workflow

| Field | Content |
|-------|---------|
| **Description** | Governed diff preview → approve/reject → validate lock + git → apply → proof; heartbeat locks (**FIX 003**) aligned. |
| **Scope** | Backend validate/apply routes; extension viewer; enforcement with **E03** phase gates for implementation directives. |
| **Dependencies** | **100P**, **100M**, **100E**; **E03**. |
| **Risks** | Bypass via external editors — documented residual risk (**FIX 001**). |

---

### E09 — Proof + Audit + Manifest System

| Field | Content |
|-------|---------|
| **Description** | **Work manifest** execution ledger UI; **proof review** (ACCEPT / REJECT / REQUEST FIX / ESCALATE); audit linkage state ↔ proof ↔ memory ↔ patch. |
| **Scope** | Manifest aggregate API; proof package assembly; decision endpoints with required rejection reason; bind **`STATE_TRANSITION`** payloads. |
| **Dependencies** | **E03**; existing `ProofObject`, audits. |
| **Risks** | UI guessing manifest — server-driven rows only. |

---

### E10 — Bug-Check / QA Flow

| Field | Content |
|-------|---------|
| **Description** | Post-accept **validation runs** (smoke, tests, lint, patch sanity, etc.); **no silent skip**; WAIVED visible; QA/Test + Debugger + Reviewer path per blueprint. |
| **Scope** | `validation_run` abstraction; status in manifest; compose smoke optional job; integration with Nike/worker. |
| **Dependencies** | **E03** (BUG_CHECKING phase); **E09** (proof acceptance trigger); **E04** (env checks). |
| **Risks** | Long-running CI — async jobs + polling UX. |

---

## 3. Implementation directives (by epic)

### E01 — VS Code Workbench

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **WB_001** | Activity bar + panel skeleton + config | API base URL; auth placeholder | Shell layout; empty panels wired | Three regions + status bar render; settings load | Extension launches; screenshot |
| **WB_002** | Backend-driven action enablement | `execution-ui-state` schema | Buttons bind to `actions_allowed` only | No enabled action without server flag | Integration test or manual script |
| **WB_003** | Center document host | Architecture artifact API | Markdown/editor webview for doc | Load/save draft per API contract | Recorded session |
| **WB_004** | Debug mode | Feature flag | Raw correlation IDs / optional JSON pane | Toggle hides/shows internals | Screenshot diff |

---

### E02 — Shared Agent Thread

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **THR_001** | Conversation schema + migrations | Blueprint metadata fields | `conversation_message` (or equivalent) table | Single thread key per scope; indexes | Migration + unit tests |
| **THR_002** | Post/list/thread APIs | User + agent messages | Paginated GET; POST with role | Role badge data persisted; ordering key | pytest + OpenAPI snapshot |
| **THR_003** | RAG ingest hook | THR_002 events | Memory rows + vector queue | Agent messages searchable cross-role | Retrieval integration test |
| **THR_004** | Extension thread UI | THR_002 | Agent selector + unified thread | Switch agent without new thread id | UI recording |

---

### E03 — State Engine

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **STATE_001** | State schema + enums + mapping doc | APP_BLUEPRINT UI states | `directive_phase` / gate columns; LLD mapping table | Illegal enum combos rejected at codegen/review | Published mapping + review ACK |
| **STATE_002** | `StateTransitionService` | Current row FOR UPDATE | Transition + audit/log | No raw status UPDATE outside service | Unit tests + grep CI rule |
| **STATE_003** | Gate enforcement integration | Project gate rows | `GateEvaluationService`; scaffold/workflow pre-flight | 409 when gate fails | pytest scenarios |
| **STATE_004** | Audit logging per transition | STATE_002 | `STATE_TRANSITION` payload schema | Required fields present | Audit query sample |
| **STATE_005** | Transition + gate REST APIs | Service layer | POST verbs or domain routes | Idempotency documented | Contract tests |
| **STATE_006** | UI state aggregation endpoint | Directives + gates + prereqs | `execution-ui-state` JSON | Matches blueprint § UI alignment | Golden JSON test |

---

### E04 — Prerequisite + Environment Gate

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **GATE_001** | Prerequisite item model + APIs | Blueprint categories | CRUD + PATCH states | WAIVED requires reason | pytest |
| **GATE_002** | Auto probes (health, files, compose manifest) | Repo snapshot / settings | Probe results → item states | Dockerfile/env/lock detected | Integration test |
| **GATE_003** | `build_allowed` aggregate | GATE_001–002 | Single gate endpoint consumed by STATE_003 | BLOCKING blocks scaffold | E2E 409 |
| **GATE_004** | Extension readiness strip | GATE_003 | Environment checklist UX | Mirrors server | Manual checklist |

---

### E05 — Project Type + Structure

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **PROJ_001** | Project type classifier + API | Intake text | Type + confidence + override | 12 types from blueprint | pytest |
| **PROJ_002** | Canonical structure templates | PROJ_001 | Tree proposals per type | Matches blueprint examples | Snapshot tests |
| **PROJ_003** | Dual approval + versioning | Artifacts | Approved arch + structure ids | Server denies scaffold otherwise | API tests |
| **PROJ_004** | Scaffold job | PROJ_003 + GATE_003 | Idempotent file creation | Audit trail | Dry-run + sample repo |

---

### E06 — RAG / Memory

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **RAG_001** | Ingest + chunking pipeline | source_type rules | Chunks + metadata | All mandatory metadata fields | Validation tests |
| **RAG_002** | Hybrid query API | Scopes + budget | Ranked context bundle | Latency targets documented | Load test note |
| **RAG_003** | Repo indexer + staleness | Git refs | `stale-report` | commit_sha mismatch surfaced | Integration |
| **RAG_004** | Degraded mode | Vector outage | Structured-only + UI flag | No silent empty | Chaos test |

---

### E07 — Model Cadre + Routing

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **MODEL_001** | Cadre registry persistence | Roles | Profile assignments | Matches blueprint roles | pytest |
| **MODEL_002** | Readiness probe APIs | Local backends | status/refresh endpoints | READY/MISSING/DEGRADED | Contract tests |
| **MODEL_003** | Extension Model Cadre panel | MODEL_002 | Panel per blueprint | Install commands visible | Screenshot |
| **MODEL_004** | 100R integration hardening | 000G policy | Escalation audits | No silent external | Audit chain test |

---

### E08 — Patch + Lock + Apply

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **PATCH_001** | Validate/apply API alignment | 100E simulated-mutation | Thin routes per blueprint | Lock + git integrity | pytest |
| **PATCH_002** | Extension diff viewer | PATCH_001 | Preview/reject/apply | Matches gate phase | Manual proof |
| **PATCH_003** | Heartbeat + stale UX | FIX 003 | IDE heartbeat loop | No edit on stale | Scenario test |

---

### E09 — Proof + Audit + Manifest

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **PROOF_001** | Manifest aggregate API | Ledger + audits | Work manifest rows | Single source for UI | Golden JSON |
| **PROOF_002** | Proof package endpoint | Proofs + tests | Review payload | Summary + artifacts | pytest |
| **PROOF_003** | Proof decision API | ACCEPT/REJECT + reason | STATE transitions | Reject requires reason | Audit verification |

---

### E10 — Bug-Check / QA

| ID | Title | Inputs | Outputs | Success criteria | Proof |
|----|-------|--------|---------|------------------|-------|
| **QA_001** | `validation_run` model | Modes enum | Persisted runs + logs | WAIVED visible | Migration + tests |
| **QA_002** | Trigger + status APIs | PROOF acceptance | Async jobs | Status in manifest | Worker test |
| **QA_003** | QA/Test + Debugger hooks | QA_001 | Agent-invoked validation | Blueprint ordering | E2E scenario |

---

## 4. Build order (strict)

Phases are **sequential** within each band unless noted. Dependencies flow **downward**.

```text
Phase A — Foundation (blocking)
  A1. STATE_001 — schema + mapping (extends DB alongside existing enums)
  A2. STATE_002 — StateTransitionService
  A3. STATE_004 — audit payload contract
  A5. STATE_005 — core transition APIs (subset)

Phase B — Gates + environment (parallelizable after A2)
  B1. GATE_001 — prerequisite model
  B2. GATE_002 — probes (env governance checks)
  B3. GATE_003 — build_allowed aggregate
  B4. STATE_003 — wire gates into scaffold + workflow pre-flight

Phase C — Project + structure
  C1. PROJ_001 → PROJ_002 → PROJ_003 → PROJ_004

Phase D — Memory / RAG (parallel with C after A1)
  D1. RAG_001 → RAG_002 → RAG_003 → RAG_004

Phase E — Shared thread (needs D1 ingest hooks)
  E1. THR_001 → THR_002 → THR_003 → THR_004

Phase F — Model cadre (parallel; depends on registry clarity with 100R)
  F1. MODEL_001 → MODEL_002 → MODEL_003 → MODEL_004

Phase G — Aggregation + UI shell
  G1. STATE_006 — execution-ui-state
  G2. WB_001 → WB_002 → WB_003 → WB_004

Phase H — Patch / lock UX hardening
  H1. PATCH_001 → PATCH_002 → PATCH_003

Phase I — Proof / manifest
  I1. PROOF_001 → PROOF_002 → PROOF_003

Phase J — QA / bug-check
  J1. QA_001 → QA_002 → QA_003
```

**Interpretation:** **Memory/RAG** and **project structure** can proceed in parallel once **state foundation** exists; **UI workbench** blocks on **STATE_006**; **model router** cadre UI blocks on **MODEL_002** and policy (**100R**); **patch workflow** assumes **100P/M** baseline; **QA flow** closes after proof decisions.

---

## 5. Dependencies (cross-epic / directive mapping)

```text
STATE_001 → STATE_002 → STATE_003 → STATE_005 / STATE_006
          ↘ GATE_001 → GATE_002 → GATE_003 ────────┘
PROJ_* ────────────────────────────────────────────┘ (scaffold/start-build)
RAG_* ∥ PROJ_* (after STATE_001)
THR_* after THR_001 + RAG_001 (ingest)
MODEL_* ∥ (after STATE_001 for degraded flags)
WB_* after STATE_006 (+ partial MODEL_* for cadre panel)
PATCH_* after gates + existing locks
PROOF_* after STATE_002 + audits
QA_* after PROOF_003 + STATE mapping for BUG_CHECKING
```

| Consumer | Depends on |
|----------|------------|
| **E01** WB_* | **STATE_006**, **GATE_003**, **MODEL_002** |
| **E02** THR_* | **RAG_001**, **STATE_006** |
| **E03** STATE_* | Existing `directives`, `task_ledger`, `audit_events` |
| **E04** GATE_* | **STATE_002** (gate enforcement wiring) |
| **E05** PROJ_* | **STATE_003**, **GATE_003**, **RAG_*** (artifacts) |
| **E06** RAG_* | Memory/Chroma schema; optional **100R** for embed |
| **E07** MODEL_* | **100R** policy; **STATE_006** flags |
| **E08** PATCH_* | **100E/100P**; **STATE_003**; locks API |
| **E09** PROOF_* | Audits, proofs, ledger |
| **E10** QA_* | **PROOF_003**, Nike/worker |

---

## 6. Data model plan

**Authority:** Postgres is source of truth; extension holds **no** authoritative lifecycle fields.

| Structure | Purpose | Key fields / notes |
|-----------|---------|-------------------|
| **directives** | Directive lifecycle | Existing: `id`, `status` (`DirectiveStatus`), `workspace_id`, `project_id`, … **Extend (LLD):** optional `directive_phase` (blueprint UI vocabulary), `blocked_reason_code`, `blocked_payload_json`, `updated_at` |
| **task_ledger** | Per-directive task state | Existing: `current_state` (`TaskLifecycleState`), `current_agent_role`, `directive_id` — transitions via **StateTransitionService** only |
| **state_transition_log** (recommended) | Append-only transitions | `entity_type`, `entity_id`, `from_state`, `to_state`, `transition_name`, `actor_type`, `actor_id`, `correlation_id`, `payload_json`, `created_at` — *or* normalized **`STATE_TRANSITION`** audits as sole log (pick one primary in implementation directive) |
| **project_gates** (or columns on `projects`) | PLAN / STRUCTURE / PREREQ clearance | `project_id`, `plan_approved_artifact_id`, `structure_approved_artifact_id`, `prerequisites_cleared_at`, `environment_cleared_at`, `version` |
| **prerequisite_item** | Gate checklist | `id`, `project_id`, `category`, `title`, `validation_type`, `state` (READY/MISSING/DEGRADED/WAIVED/BLOCKING), `waiver_reason`, timestamps |
| **conversation_message** (or equivalent) | Shared agent thread | `project_id`, `directive_id`, `role`, `author_type`, `body`, `memory_sequence`, `correlation_id`, `created_at` |
| **memory_entries** + vector metadata | RAG / structured memory | Align with blueprint metadata: `project_id`, `directive_id`, `task_id`, `source_type`, `source_path`, `commit_sha`, `vector_state`, `visibility_scope`, … |
| **proof_objects** | Proof artifacts | Existing types; link to directive + transition |
| **audit_events** | Non-repudiation | `AuditEventType` includes **`STATE_TRANSITION`**; payload binds transition ↔ proof ↔ patch ids |
| **validation_run** | Bug-check | `id`, `directive_id`, `mode`, `status`, `waived_reason`, `log_ref`, `started_at`, `completed_at` |

**Constraints:** No relaxation of blueprint gates; waivers **audited**; backend validates all writes.

---

## 7. API plan

Prefix **`/api/v1/...`** (with deploy **`TRIDENT_BASE_PATH`** as today). Below: **existing** vs **new** (blueprint/LLD).

### 7.1 Existing endpoints (inventory — current spine)

| Area | Methods | Path pattern |
|------|---------|----------------|
| Health / version | GET | `/health`, `/version` (non-v1 as wired) |
| System | GET | `/v1/system/model-router-status`, `/v1/system/schema-status` |
| Directives | GET, POST | `/v1/directives/`, `/v1/directives/{id}`, `/v1/directives/{id}/workflow/run` |
| Memory | GET, POST | `/v1/memory/project/{project_id}`, `/v1/memory/directive/{directive_id}`, `/v1/memory/write`, `/v1/memory/retry-vector-index` |
| Locks | GET, POST | `/v1/locks/status`, `/v1/locks/active`, `/v1/locks/heartbeat`, `/v1/locks/force-release`, `/v1/locks/acquire`, `/v1/locks/release`, `/v1/locks/simulated-mutation` |
| Patches | POST | `/v1/patches/propose`, `/v1/patches/reject`, `/v1/patches/apply-complete` |
| MCP | POST | `/v1/mcp/classify`, `/v1/mcp/execute` (see `mcp_router`) |
| Subsystem router | POST | `/v1/router/route` |
| Nike | POST, GET | `/v1/nike/events`, `/v1/nike/events/{event_id}` |
| IDE | POST, GET | `/v1/ide/chat`, `/v1/ide/action`, `/v1/ide/status/{directive_id}`, `/v1/ide/proof-summary/{directive_id}` |

### 7.2 New endpoints required (by concern)

| Concern | Suggested routes | Epic |
|---------|------------------|------|
| UI aggregate | `GET /v1/projects/{id}/execution-ui-state`, `GET /v1/directives/{id}/execution-ui-state` | E03 |
| State transitions | Domain-specific POSTs or `POST /v1/directives/{id}/transitions` (if unified) | E03 |
| Project gates | `GET/POST /v1/projects/{id}/gates/*`, `GET /v1/projects/{id}/gates` | E03–E04 |
| Prerequisites | `GET/POST /v1/projects/{id}/prerequisites`, `PATCH .../items/{item_id}`, `POST .../validate`, `GET .../prerequisites/gate` | E04 |
| Project type + structure | `POST .../classify-type`, `POST .../architecture/generate`, `POST .../structure/propose`, `POST .../structure/approve`, `POST .../scaffold` | E05 |
| RAG | `POST /v1/rag/ingest`, `POST /v1/rag/query`, `POST /v1/rag/index/repo`, `GET /v1/rag/health`, `POST /v1/rag/reindex`, `GET /v1/rag/stale-report` | E06 |
| Shared thread | `GET/POST /v1/projects/{id}/conversation` (or directive-scoped variant) | E02 |
| Model cadre | `GET/POST /v1/model-cadre/status`, `POST .../refresh`, `POST .../assign`, `GET .../recommendations` | E07 |
| Proof review | `GET /v1/directives/{id}/proof-package`, `POST /v1/directives/{id}/proof/decision` | E09 |
| Manifest | `GET /v1/projects/{id}/manifest` | E09 |
| QA / bug-check | `POST /v1/directives/{id}/validation`, `GET .../validation/{run_id}` | E10 |

Exact naming is **implementation directive**-owned; behavior must match **APP_BLUEPRINT_001** and **STATE_ENGINE** addendum.

---

## 8. UI plan (VS Code extension — UI only)

**Principle:** Extension **displays** and **invokes** APIs; **backend** computes `actions_allowed`, gates, and lifecycle.

| Panel | Responsibility | State binding |
|-------|----------------|---------------|
| **Left — intake + roster** | Project intake; agent cards (status, model, task, memory access) | `execution-ui-state` + model cadre endpoint |
| **Center — document workspace** | Architecture, structure tree, phases, acceptance criteria | Project/artifact GET/PATCH; enablement from gates |
| **Right — team room** | Shared thread; agent selector above composer | Conversation POST/GET; **no** per-agent thread ids |
| **Status bar** | Lock, model readiness, directive phase, warnings | Locks GET + cadre status + `execution-ui-state.blocked` |

**Event flow (read/write):**

```text
User action → Extension command → Trident API (POST/PATCH)
         → Response includes updated execution-ui-state fragment or client refetch
         → UI re-renders panels; buttons disabled if !actions_allowed
Server push (future): optional SSE/WebSocket; not required for Phase 1 if polling after mutations
```

**Debug mode:** Optional raw JSON / correlation id display — **never** default.

---

## 9. Phased delivery (rollout)

Product-facing phases (**orthogonal** to technical A–J build bands in §4):

| Phase | Goal | Epics / focus |
|-------|------|----------------|
| **Phase 1 — Minimal system** | Single-user governed path: state foundation + gates + basic UI shell + manifest read | **E03** (STATE_001–006 minimal), **E04** (GATE_001–003), **E09** (PROOF_001), **E01** (WB_001–002), existing directive/list |
| **Phase 2 — Shared / team features** | Shared thread + RAG ingest + project/structure approval + prerequisite UX | **E02**, **E06** (RAG_001–002), **E05** (PROJ_001–003), **GATE_004**, **WB_003** |
| **Phase 3 — Advanced orchestration** | Proof decisions API, patch UX hardening, model cadre panel, validation runs, scaffold automation | **PROOF_002–003**, **E08**, **E07**, **E10**, **PROJ_004**, **RAG_003–004** |
| **Phase 4 — Performance / polish** | Latency, rerank, caching, ETags on aggregates, observability, golden-path UX | Harden **STATE_006**, **RAG_002**, concurrent-user testing, status bar refinements |

**Constraint:** Gates and state rules **unchanged** across phases — only **scope** of delivered surfaces expands.

---

## 10. Risks (system-level)

| Risk | Impact | Mitigation |
|------|--------|------------|
| Dual writers to directive/ledger status | Undefined behavior, audit gaps | **StateTransitionService** + CI grep; LangGraph/Nike paths audited |
| Client-side gate inference | Bypass UX, false “build ready” | **`actions_allowed`** only from API; extension tests |
| Prerequisite / env waiver creep | Production builds on broken env | WAIVED reason + audit; optional secondary approval |
| RAG / vector outage | Silent poor answers | Degraded mode + UI flag; structured fallback |
| Concurrent workflows / races | Duplicate scaffold or runs | Row locks, idempotency keys, 409 policy |
| Model cadre / 100R drift | Wrong agent model | Registry versioning; readiness refresh |
| Scope creep (dashboard) | Violates blueprint “opinionated simple” | UI review against **APP_BLUEPRINT_001** § UI principles |

---

## 11. Estimated work

| Epic | Rough effort (eng-weeks) | Notes |
|------|---------------------------|--------|
| **E03** State engine | 8–11 | Critical path |
| **E04** Gates + env | 4–7 | Overlaps STATE_003 |
| **E05** Project/structure | 4–6 | Parallel after A2 |
| **E06** RAG | 6–10 | Parallel with E05 |
| **E02** Thread | 3–5 | After RAG ingest hook |
| **E07** Model cadre | 4–8 | Tied to **100R** maturity |
| **E01** Workbench | 6–10 | After STATE_006 |
| **E08** Patch/lock UX | 3–5 | Builds on existing APIs |
| **E09** Proof/manifest | 4–6 | |
| **E10** QA flow | 4–6 | Async worker complexity |

**Critical path (longest practical chain):** **STATE_001 → STATE_002 → GATE_001–003 → STATE_003 → STATE_006 → WB_002** → then parallel **PROJ_***, **RAG_***, **THR_***, **PROOF_***, **QA_***.

**Total (indicative):** ~46–74 eng-weeks **wall-clock less** with parallel squads; critical path ~**20–28** weeks single-threaded equivalent.

---

## 12. Alignment with existing implementation

| Area | Today (repo) | LLD fills |
|------|----------------|-----------|
| Spine / ledger | `100C`, `DirectiveStatus`, `TaskLifecycleState` | STATE_* mapping + gates |
| IDE | `100K`, `100P`, partial **100M**/patches | WB_*, PATCH_*, STATE_006 |
| Memory | `100D`, Chroma | RAG_* |
| Router | `100G`, `100R` scaffold | MODEL_* |
| Nike | `100O` | STATE_003 Nike handler rules |
| Locks | `100E`, FIX 003 plan | PATCH_003, GATE_* env |

---

## 13. Issuance rule

Each **implementation directive** (`WB_001`, `STATE_002`, …) must be promoted to a **`TRIDENT_IMPLEMENTATION_DIRECTIVE_*`** (or numbered program file) with acceptance criteria and proof **before** engineering **Start Build** on that slice.

---

## 14. Acceptance of this LLD

| Gate | Requirement |
|------|-------------|
| Program review | Architect/program **ACCEPT** recorded in **`WORKFLOW_LOG.md`** |
| Manifest | Register **`APP_LLD_001`** file path in **`TRIDENT_DOCUMENT_MANIFEST_v1_0.md`** |
| Execution | **Master Execution Guide** references this file as authoritative for post-blueprint waves |

**Program ACCEPT recorded:** **`WORKFLOW_LOG.md`** — **2026-04-30**.

---

## RETURN (executive)

| Field | Value |
|--------|--------|
| **Directive** | `APP_LLD_001` |
| **Status** | **ACCEPTED** — **2026-04-30** |
| **Epics** | **E01–E10** (§2) |
| **Directives** | **WB_*, THR_*, STATE_*, GATE_*, PROJ_*, RAG_*, MODEL_*, PATCH_*, PROOF_*, QA_*** (§3) |
| **Build order** | Technical phases **A–J** (§4) |
| **Dependencies** | Graph + table (§5) |
| **Data model** | §6 |
| **API plan** | §7 |
| **UI plan** | §8 |
| **Phases** | Rollout **Phase 1–4** (§9) |
| **Risks** | §10 |
| **Estimated work** | Per-epic table + critical path (§11) |

---

**END APP_LLD_001**
