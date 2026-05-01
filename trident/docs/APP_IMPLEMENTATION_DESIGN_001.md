# APP_IMPLEMENTATION_DESIGN_001 — System Implementation Design

**Directive:** `APP_IMPLEMENTATION_DESIGN_001`  
**Status:** **ISSUED** (document **READY** — §RETURN)  
**Parent blueprint:** `trident/docs/APP_BLUEPRINT_001.md`  
**Parent LLD:** `trident/docs/APP_LLD_001.md`  

**Purpose:** **Technical design** to realize the blueprint in **services**, **data**, and **APIs**. This is **not** a restatement of product intent — see **`APP_BLUEPRINT_001`** for **why**; this document defines **how**.

**Constraint:** **No application code** in this directive. **Backend authoritative**; **extension client-only**.

---

## 1. System architecture

### 1.1 Control plane API (`trident-api`)

| Attribute | Specification |
|-----------|----------------|
| **Responsibility** | HTTP/JSON surface for IDE, web UI, automation; authn/authz boundary; request validation; orchestration entry (workflow run, patches, locks). |
| **Inputs** | Authenticated requests + correlation ids. |
| **Outputs** | JSON responses, HTTP errors (**409** invalid state), audit enqueue. |
| **Dependencies** | Postgres, optional Redis (future), settings; delegates to domain services (never embeds business rules duplicated elsewhere). |
| **Tech** | FastAPI, SQLAlchemy sessions per request, **single DB transaction** per mutating use-case where feasible. |

### 1.2 State engine

| Attribute | Specification |
|-----------|----------------|
| **Responsibility** | **Single writer** for `directives.status`, `task_ledger.current_state`, `project_gates`; append **`state_transition_log`**; emit **`STATE_TRANSITION`** audits; evaluate **gate preconditions** before scaffold/workflow/patch-apply. |
| **Inputs** | Transition requests (actor, target entity, desired transition, optional reason). |
| **Outputs** | Updated rows + log row + audit; or **409** with structured error (blueprint error schema). |
| **Dependencies** | Postgres; called from API handlers, LangGraph entry/exit hooks, Nike handlers (same code path). |
| **Implementation slice** | **`StateTransitionService`** (STATE_002+); STATE_001 provides tables/enums only. |

### 1.3 Context engine (RAG)

| Attribute | Specification |
|-----------|----------------|
| **Responsibility** | Ingest normalized text → chunk → embed → index; **query** with **mandatory `project_id` filter**; hybrid structured + vector retrieval; stale detection. |
| **Inputs** | `project_id`, directive/task scope, query text, metadata filters. |
| **Outputs** | Ranked chunks + provenance; never returns rows without **project_id match** in SQL/filter layer. |
| **Dependencies** | Postgres (`memory_entries` + payload); **Chroma** (current) namespace = `f"project:{project_id}"` or collection per project; optional **pgvector** migration path (same filter discipline). |

### 1.4 Architect intake / normalization pipeline

| Attribute | Specification |
|-----------|----------------|
| **Responsibility** | Accept uploads + chat lines tagged **`#architect`**; persist **artifact**; **extract** text (PDF/HTML/etc.); **normalize** to **`ArchitectInputEnvelope`** (§6); enqueue **Nike** or synchronous call to **Architect worker**; create/update **directives** only through **state engine**. |
| **Inputs** | Raw bytes + MIME + `project_id` + `user_id`. |
| **Outputs** | `artifact_id`, `normalized_document_id`, optional `directive_id`, rejection record. |
| **Dependencies** | Object storage or DB blob (choice in §2 **artifacts**); extractors library; **LLM via 100R** for interpretation step (governed). |

### 1.5 Orchestration layer (LangGraph + Nike)

| Attribute | Specification |
|-----------|----------------|
| **Responsibility** | **LangGraph**: compiled spine per directive run; node boundaries persist ledger/graph state. **Nike**: durable events; handlers **call state engine** — never raw SQL status updates. |
| **Inputs** | `directive_id`, event payloads. |
| **Outputs** | Graph completion, side-effect audits. |
| **Dependencies** | State engine pre-flight **before** `invoke`; existing `run_spine_workflow`. |

### 1.6 Patch / apply system

| Attribute | Specification |
|-----------|----------------|
| **Responsibility** | **Propose** unified diff (deterministic/stub today); **reject** audit; **apply-complete** → validate lock + git + **`simulated-mutation`** path → **ProofObject**. |
| **Inputs** | `PatchProposeRequest` / `PatchApplyCompleteRequest` (existing schemas). |
| **Outputs** | Diff text, proof id, correlation id. |
| **Dependencies** | Locks service, git validation service, proof repository. |

### 1.7 Collaboration + lock service

| Attribute | Specification |
|-----------|----------------|
| **Responsibility** | **File locks** per `(project_id, file_path)` active row; heartbeat; stale transition; force-release policy; **membership** authorization checks (future: §2 **`project_members`**). |
| **Inputs** | acquire/release/heartbeat/active/simulated-mutation. |
| **Outputs** | Lock row or conflict **409**. |
| **Dependencies** | `file_locks` table; **LockService** (existing pattern). |

---

## 2. Data model (concrete)

**Legend:** **✓** exists today · **+** new (required by blueprint)

### 2.1 `workspaces` ✓

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| name | VARCHAR(255) | |
| description | TEXT | nullable |
| created_by_user_id | UUID FK → users | |
| created_at, updated_at | TIMESTAMPTZ | |

### 2.2 `projects` ✓ — **extend +**

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| workspace_id | UUID FK | |
| name | VARCHAR(255) | |
| allowed_root_path | TEXT | |
| git_remote_url | TEXT | nullable |
| created_at, updated_at | TIMESTAMPTZ | |
| **slug** | VARCHAR(64) **+** | optional URL-safe id for APIs |
| **settings_json** | JSONB **+** | feature flags, default branch |

### 2.3 `project_members` **+**

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| project_id | UUID FK projects ON DELETE CASCADE | |
| user_id | UUID FK users | |
| role | VARCHAR(32) | OWNER, ADMIN, CONTRIBUTOR, REVIEWER, VIEWER |
| invited_by | UUID FK users nullable | |
| created_at | TIMESTAMPTZ | |
| **UNIQUE(project_id, user_id)** | | |

### 2.4 `directives` ✓

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| workspace_id, project_id | UUID FK | |
| title | TEXT | |
| status | VARCHAR(32) | `DirectiveStatus` string |
| graph_id | VARCHAR(255) nullable | |
| created_by_user_id | UUID FK | |
| created_at, updated_at | TIMESTAMPTZ | |
| **directive_phase** | VARCHAR(32) **+** optional | UI/numeric phase without overloading `status` |

### 2.5 `task_ledger` ✓

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| directive_id | UUID FK UNIQUE | |
| current_state | VARCHAR(32) | `TaskLifecycleState` |
| current_agent_role | VARCHAR(32) | |
| current_owner_user_id | UUID nullable | |
| last_transition_at | TIMESTAMPTZ | |
| created_at, updated_at | TIMESTAMPTZ | |

### 2.6 `state_transition_log` ✓ (STATE_001)

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| directive_id | UUID FK nullable ON DELETE SET NULL | |
| from_state | VARCHAR(64) nullable | |
| to_state | VARCHAR(64) | |
| actor_type | VARCHAR(16) | USER / AGENT / SYSTEM |
| actor_id | UUID nullable | |
| correlation_id | UUID nullable indexed | |
| reason | TEXT nullable | |
| created_at | TIMESTAMPTZ | |

### 2.7 `project_gates` ✓ (STATE_001)

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| project_id | UUID FK CASCADE | |
| gate_type | VARCHAR(32) | PLAN / STRUCTURE / PREREQS |
| status | VARCHAR(32) | GateStatus |
| approved_by | UUID FK users nullable | |
| approved_at | TIMESTAMPTZ nullable | |
| waiver_flag | BOOLEAN | |
| waiver_reason | TEXT nullable | |
| created_at, updated_at | TIMESTAMPTZ | |
| **UNIQUE(project_id, gate_type)** | | |

### 2.8 `file_locks` ✓

(Existing — see `FileLock` model: partial unique ACTIVE path, heartbeat, expires_at.)

### 2.9 `memory_entries` ✓ (= structured + vector pointer)

Acts as **context chunk lineage** (structured body + sequence); Chroma holds embedding document.

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | also Chroma doc key |
| directive_id, project_id, task_ledger_id | UUID FK | **project_id indexed for isolation** |
| agent_role, memory_kind | VARCHAR | |
| title | VARCHAR nullable | |
| body_text | TEXT | chunk text |
| payload_json | JSONB | metadata: source_path, commit_sha, source_type |
| chroma_document_id | VARCHAR nullable | |
| memory_sequence | BIGINT | |
| vector_state | VARCHAR(32) | |
| vector_last_error | TEXT nullable | |
| vector_indexed_at | TIMESTAMPTZ nullable | |
| created_at | TIMESTAMPTZ | |

**Future +:** `embedding_model_id` VARCHAR(64) for cadre versioning.

### 2.10 `proof_objects` ✓

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| directive_id | UUID FK CASCADE | |
| proof_type | VARCHAR(64) | |
| proof_uri | TEXT nullable | |
| proof_summary | TEXT nullable | |
| proof_hash | VARCHAR(128) nullable | |
| created_by_agent_role | VARCHAR(32) | |
| created_at | TIMESTAMPTZ | |

### 2.11 `audit_events` ✓ (= audit_log)

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| workspace_id, project_id, directive_id | UUID nullable FK indexed | |
| event_type | VARCHAR(64) indexed | |
| event_payload_json | JSONB | |
| actor_type | VARCHAR(32) | |
| actor_id | VARCHAR(512) nullable | **normalize to UUID string for users** in new code |
| created_at | TIMESTAMPTZ | |

### 2.12 `artifacts` **+**

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| project_id | UUID FK | |
| uploaded_by | UUID FK users | |
| storage_key | TEXT | S3 path or `blobs/{uuid}` |
| mime_type | VARCHAR(128) | |
| byte_size | BIGINT | |
| sha256 | VARCHAR(64) | |
| created_at | TIMESTAMPTZ | |

### 2.13 `normalized_documents` **+**

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| artifact_id | UUID FK artifacts nullable | chat-only intake nullable |
| project_id | UUID FK | |
| source_kind | VARCHAR(32) | chat_line / upload / paste |
| extracted_text | TEXT | |
| structure_json | JSONB | headings, code blocks, summary |
| architect_handoff_status | VARCHAR(32) | PENDING / DISPATCHED / COMPLETE |
| created_at | TIMESTAMPTZ | |

### 2.14 `conversation_messages` **+**

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| project_id | UUID FK indexed | |
| thread_id | UUID | single thread per project **v1**: `thread_id = project_id` constant |
| author_type | VARCHAR(16) | USER / AGENT / SYSTEM |
| author_user_id | UUID nullable | |
| agent_role | VARCHAR(32) nullable | |
| body | TEXT | |
| tags | VARCHAR(64)[] or JSONB | e.g. `#architect` parsed flag |
| correlation_id | UUID nullable | |
| created_at | TIMESTAMPTZ indexed | |

### 2.15 `patches` **+** (optional persistence)

Today patches are **stateless API**; blueprint requires audit trail via proofs + audits. **+** table if needed:

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| project_id, directive_id | UUID | |
| file_path | TEXT | |
| unified_diff | TEXT | |
| status | VARCHAR(32) | PROPOSED / REJECTED / APPLIED |
| correlation_id | UUID | |
| created_at | TIMESTAMPTZ | |

**Decision:** **Phase 1** rely on **audit_events** (`PATCH_*`) + **proof_objects**; add **`patches`** table when UI requires history paging.

### 2.16 `validation_runs` **+** (bug-check)

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| directive_id | UUID FK | |
| mode | VARCHAR(64) | smoke / pytest / lint / … |
| status | VARCHAR(32) | RUNNING / PASS / FAIL / WAIVED |
| log_uri | TEXT nullable | |
| waived_reason | TEXT nullable | |
| started_at, completed_at | TIMESTAMPTZ | |

---

## 3. API design

**Base:** `{PUBLIC_BASE}/api/v1`  
**Auth:** `Authorization: Bearer <access_token>` **+** `X-Trident-Workspace-Id` where scope requires (exact header names in OpenAPI). **Existing** routes largely **unchecked** — mark **changed** when middleware applied.

### 3.1 Summary table

| Route | Method | Request / Response | Auth | Status |
|-------|--------|-------------------|------|--------|
| `/health`, `/ready` | GET | plain | none | **existing** |
| `/version` | GET | version JSON | none | **existing** |
| `/v1/system/schema-status` | GET | | optional | **existing** |
| `/v1/system/model-router-status` | GET | | optional | **existing** |
| `/v1/directives/` | POST | `CreateDirectiveRequest` → `DirectiveDetailResponse` | **changed** JWT + project membership |
| `/v1/directives/` | GET | list | **changed** | |
| `/v1/directives/{id}` | GET | detail | **changed** | |
| `/v1/directives/{id}/workflow/run` | POST | query params → `WorkflowRunResponse` | **changed** + **state engine preflight** |
| `/v1/directives/{id}/transition` | POST | `{to_status, reason}` → directive | **new** | wraps StateTransitionService |
| `/v1/projects/` | POST | create project | **new** | |
| `/v1/projects/{id}` | GET/PATCH | project | **new** | |
| `/v1/projects/{id}/members` | GET/POST/PATCH/DELETE | membership | **new** | |
| `/v1/projects/{id}/gates` | GET | aggregate gate + prereq | **new** | |
| `/v1/projects/{id}/gates/{type}` | POST | approve/waive | **new** | |
| `/v1/projects/{id}/conversation` | GET/POST | messages | **new** | |
| `/v1/projects/{id}/artifacts` | POST multipart | artifact id | **new** | |
| `/v1/projects/{id}/execution-ui-state` | GET | §9 payload | **new** | |
| `/v1/projects/{id}/rag/query` | POST | `{query, filters, budget}` | **new** | |
| `/v1/projects/{id}/rag/ingest` | POST | `{memory_entry_id}` or chunk spec | **new** | |
| `/v1/model-cadre/status` | GET | roster | **new** | |
| `/v1/memory/...` | | | **existing** | tighten **`project_id`** match on reads |
| `/v1/locks/...` | | | **existing** | **changed** membership |
| `/v1/patches/...` | | | **existing** | **changed** gate preflight on apply |
| `/v1/nike/events` | POST | | **existing** | **changed** validate producer |
| `/v1/mcp/...` | POST | | **existing** | |
| `/v1/router/route` | POST | | **existing** | |
| `/v1/ide/chat` | POST | | **existing** | **changed** route `#architect` to intake |

**OpenAPI:** Each **new/changed** route gets **Pydantic models** in `app/schemas/` — namespaced `projects.py`, `conversation.py`, `execution_ui.py`.

---

## 4. State engine design

### 4.1 Enums (authoritative strings)

- **`DirectiveStatus`** — full set per **`app/models/enums.py`** (includes blueprint extensions).  
- **`TaskLifecycleState`** — idem.  
- **`GateStatus`** — READY / MISSING / DEGRADED / WAIVED / BLOCKING.  
- **`ProjectGateType`** — PLAN / STRUCTURE / PREREQS.

### 4.2 Transition matrix (directive.status — excerpt)

Rows **from** → Columns **to** allowed (**✓**) — illustrative; full matrix in code as **`ALLOWED_DIRECTIVE_TRANSITIONS: dict[tuple[str,str], bool]`**.

| From \\ To | ISSUED | ACKNOWLEDGED | PLANNING | PLAN_APPROVED | BUILDING | PROOF_RETURNED | REVIEW | COMPLETE |
|------------|--------|---------------|----------|---------------|----------|----------------|--------|----------|
| DRAFT | ✓ | | ✓ | | | | | |
| ISSUED | | ✓ | | | | | | |
| PLANNING | | | | ✓ | | | | |
| PLAN_APPROVED | | | | | ✓* | | | |
| BUILDING | | | | | | ✓ | | |
| PROOF_RETURNED | | | | | | | ✓ | |

\*Requires **`project_gates`** all non-BLOCKING and model readiness policy.

**Invalid:** any pair not in map → **409** `transition_not_allowed`.

### 4.3 Validation rules

1. Load **`directives`** + **`task_ledger`** + **`project_gates`** **FOR UPDATE**.  
2. Verify actor **membership** + role can perform transition (RBAC matrix).  
3. Check **gate preconditions** for transitions into **BUILDING** / **scaffold**.  
4. Insert **`state_transition_log`** then update status then **`audit_events`**.  
5. **Commit** single transaction — rollback on any failure.

### 4.4 Enforcement location

| Layer | Behavior |
|-------|----------|
| **API** | All mutating handlers call **`StateTransitionService`** — **never** `directive.status = x` in routes. |
| **LangGraph** | **`run_spine_workflow`** wraps **`update_directive_status`** → refactor to service-only. |
| **Nike** | Handlers invoke service with **`actor_type=SYSTEM`**. |

### 4.5 Blocking invalid transitions

- **Compile-time:** exhaustive tests on matrix symmetry where required.  
- **Runtime:** lookup failure → **HTTP 409** + `{ error_code, current_state, attempted, allowed_next[], correlation_id }`.

---

## 5. Context engine design

### 5.1 Storage

| Tier | Technology | Role |
|------|------------|------|
| **Structured** | Postgres `memory_entries` | canonical text + metadata + `project_id` **NOT NULL** |
| **Vector** | **Chroma** (current): **one collection per `project_id`** OR metadata filter `project_id` **required** on every query | embeddings |
| **Future** | **pgvector** column on `memory_chunks` **+** table per project id prefix | same filter invariant |

### 5.2 Indexing strategy

1. Normalize ingest → chunk (size/overlap from settings).  
2. Write **`memory_entries`** with `project_id`, `directive_id`, payload `source_path`, `commit_sha`.  
3. Embed batch → upsert Chroma with **`where {"project_id": "..."}`** filter metadata on every query.  
4. Mark **`vector_state`**.

### 5.3 Query flow

```
Client POST /rag/query { project_id, query, top_k, directive_id? }
  → API asserts project_id == token scope
  → SQL prefilter (optional structured facts)
  → Chroma.query(where={"project_id": ...})
  → merge + rerank (optional)
  → return chunks[] with memory_entry ids
```

### 5.4 Cross-project retrieval guarantee

- **API layer:** reject if `project_id` absent or mismatched with JWT scope.  
- **Chroma layer:** **mandatory** `where` clause on `project_id`; integration test asserts two-project corpus isolation.  
- **SQL layer:** every `memory_entries` SELECT includes **`WHERE project_id = :pid`**.

---

## 6. Intake + normalization pipeline

### 6.1 Flow

```
Upload/chat → POST /projects/{id}/artifacts OR conversation message
  → store raw (artifacts table / blob)
  → job: extract text (pdfminer / mammoth / plain)
  → normalized_documents row (extracted_text + structure_json)
  → if #architect or upload flagged actionable → enqueue Nike ARCHITECT_INTAKE
  → Architect worker reads normalized_documents PENDING
  → produces directive proposal OR rejection → StateTransitionService creates ISSUED directive
```

### 6.2 Architect input contract (`ArchitectInputEnvelope`)

```json
{
  "project_id": "uuid",
  "normalized_document_id": "uuid",
  "trigger": "HASHTAG_ARCHITECT | UPLOAD",
  "user_id": "uuid",
  "correlation_id": "uuid",
  "structured_outline": { },
  "raw_excerpt": "string<=50000"
}
```

---

## 7. Collaboration + locking model

| Topic | Design |
|-------|--------|
| **Granularity** | One **ACTIVE** lock per **`(project_id, file_path)`** (partial unique index ✓). |
| **Acquire** | Validates membership + directive binding + TTL optional. |
| **Heartbeat** | **`POST /locks/heartbeat`** refreshes **`last_heartbeat_at`**; stale policy per FIX 003. |
| **Release** | Idempotent; allows stale recovery paths. |
| **Conflict** | Second acquire → **409** with holder metadata. |
| **Ownership** | **`locked_by_user_id` + `locked_by_agent_role`**; matches patch apply identity checks. |

---

## 8. Patch / apply pipeline

| Stage | Behavior |
|-------|----------|
| **Propose** | Client sends before/after → server computes unified diff + summary (deterministic). |
| **Validate (apply)** | Lock held + path under `allowed_root_path` + git sanity via **`simulated-mutation`** internals. |
| **Merge/apply** | Server-side write + **`GIT_DIFF`** proof + audits. |
| **Rollback** | **No auto git revert** in v1 — operator issues revert directive; document explicitly in UI. |

---

## 9. UI ↔ backend contract

### 9.1 `GET /v1/projects/{project_id}/execution-ui-state`

**Response (`ExecutionUiState`):**

```json
{
  "project_id": "uuid",
  "directive": { "id": "uuid", "status": "string", "phase": "string|null" },
  "ledger": { "current_state": "string", "owner_role": "string" },
  "gates": {
    "plan": { "status": "READY|...", "waiver": false },
    "structure": { },
    "prereqs": { }
  },
  "model_readiness": { "overall": "READY|DEGRADED|FAIL", "by_role": {} },
  "blocked": { "is_blocked": false, "reasons": [] },
  "actions_allowed": {
    "send_chat": true,
    "trigger_architect": true,
    "approve_plan": false,
    "start_build": false,
    "propose_patch": true,
    "apply_patch": false
  },
  "updated_at": "iso8601"
}
```

### 9.2 `actions_allowed` logic

Computed **only server-side** from status + gates + locks + membership role — **never** trust client flags.

### 9.3 Polling vs push

**Phase 1:** client **polls** `execution-ui-state` after mutations + **15–30s** backoff when idle.  
**Phase 3:** optional **SSE** `/v1/projects/{id}/events` subscription.

---

## 10. Implementation plan

| Epic | Tasks (ordered) | Depends on |
|------|-----------------|------------|
| **Auth + membership** | JWT middleware; `project_members`; authorize helpers | — |
| **State engine** | STATE_002 service; wire directives API; LangGraph refactor | STATE_001 ✓ |
| **execution-ui-state** | Aggregator read model | state + gates |
| **Conversation + #architect** | `conversation_messages`; parser; Nike handler | membership |
| **Artifacts + normalized_documents** | upload API; extract jobs | storage driver |
| **RAG query hardening** | forced project filter tests | memory |
| **Proof decisions + validation_runs** | POST proof/decision; QA worker | state |
| **Model cadre APIs** | status/refresh | 100R |

**Critical path:** Auth/membership → StateTransitionService → execution-ui-state → conversation/intake → RAG enforcement tests.

---

## 11. Risks + failure modes

| Risk | Failure mode | Mitigation |
|------|--------------|------------|
| **Race** | Double workflow run | Idempotency key on `workflow/run`; DB unique constraint on active run nonce |
| **State drift** | Client shows stale buttons | ETag on `execution-ui-state`; short TTL |
| **Lock deadlock** | Heartbeat missed | Stale transition + takeover policy (FIX 003) |
| **Context leakage** | Wrong `project_id` in Chroma | Mandatory where-clause + CI integration test |
| **Model unavailable** | Execution starts anyway | `actions_allowed.start_build=false`; readiness gate |

---

## 12. Estimated effort

| Subsystem | Eng-weeks (indicative) |
|-----------|-------------------------|
| Auth + membership | 3–5 |
| State engine service + matrix | 6–8 |
| execution-ui-state | 2–3 |
| Intake pipeline + artifacts | 5–8 |
| Conversation thread | 3–4 |
| RAG isolation hardening + query API | 4–6 |
| Proof/decision + validation_runs | 4–6 |
| Patch gate integration | 2–3 |
| Model cadre endpoints | 3–5 |

**Total:** ~32–48 eng-weeks parallelized bands. **Critical path:** ~**12–16** weeks single-threaded equivalent.

---

## RETURN — `APP_IMPLEMENTATION_DESIGN_001`

| Field | Value |
|--------|--------|
| **Directive** | `APP_IMPLEMENTATION_DESIGN_001` |
| **Status** | **READY** |
| **System architecture** | §1 |
| **Data model** | §2 |
| **API design** | §3 |
| **State engine** | §4 |
| **Context engine** | §5 |
| **Intake pipeline** | §6 |
| **Collaboration model** | §3 blueprint + §7 locks/membership |
| **Patch pipeline** | §8 |
| **UI contract** | §9 |
| **Implementation plan** | §10 |
| **Risks** | §11 |
| **Estimated work** | §12 |

---

**END APP_IMPLEMENTATION_DESIGN_001**
