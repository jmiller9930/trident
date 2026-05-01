# APP_BLUEPRINT_001 — Trident Product Blueprint (Unified)

**Directive:** `APP_BLUEPRINT_001_UNIFIED_REWRITE` · **Status:** **ISSUED** (document **READY** — see §RETURN)  
**Audience:** Engineering  
**Source:** Architecture  
**Purpose:** Single canonical definition of Trident **system behavior**, **contracts**, and **enforcement** — end-to-end.

**Supersedes:** Fragmented addendum-only structure in prior revisions of this file. **This file alone** is the product blueprint; do not treat older append-only addenda as parallel sources of truth.

**Implementation:** No code authorized by this document alone — follow **`APP_LLD_001`** and issued implementation directives.

---

## 1. Product model

| Principle | Requirement |
|-----------|-------------|
| **Authority** | The **backend workspace** is the **authoritative source of truth** for all durable product state. |
| **Project** | Each **project** is an **isolated workspace** containing: **repo** linkage, **agent stack** configuration, **context (RAG)** namespace, **directives**, **lifecycle state**, **members**, and **artifacts**. |
| **VS Code extension** | **Thin client:** connect, authenticate (work account), select project, submit work, **render backend-supplied state**. No orchestration brain in the extension. |

**Core rule:** **No durable state exists only in the client.** Cache may exist for UX; **writes** and **truth** live on the backend.

---

## 2. User workflow

| Step | Behavior |
|------|----------|
| 1 | User installs extension |
| 2 | Connects to backend |
| 3 | Authenticates (work account) |
| 4 | Creates or joins **project** |
| 5 | Uploads or submits material (any supported format — §5) |
| 6 | Uses **shared chat** (§3): **discussion by default**; **`#architect`** triggers Architect intake (§4) |
| 7 | Architect processes normalized input |
| 8 | System enters **governed directive lifecycle** (§7) |
| 9 | User observes, reviews, approves per gates and proof loop (§§8–12) |

---

## 3. Collaboration model

| Topic | Rule |
|-------|------|
| **Chat** | **Single shared chat per project** — all members see the same conversation and backend-visible state. |
| **Human roles** | **OWNER**, **ADMIN**, **CONTRIBUTOR**, **REVIEWER**, **VIEWER** — permission model for project membership and approvals (distinct from **agent roles**). |
| **Discussion vs execution** | Collaboration is **open** in discussion; **execution** is **controlled** via **state machine**, **locks**, and **Architect routing**. |
| **Ownership** | **Ownership enforced per task / directive** as recorded in ledger. |
| **Parallelism** | Parallel human or agent attempts allowed only as **isolated attempts** merged through governed transitions — **no silent overwrite** of authoritative state. |

---

## 4. Architect intake model

| Rule | Detail |
|------|--------|
| **Gate** | **All actionable execution intent** must go through the **Architect** path — not direct human → Engineer/Reviewer/etc. for governed work. |
| **Trigger** | **`#architect`** in shared chat (primary UX trigger). |
| **Architect behavior** | Interprets input; validates against **development plan**, **architecture**, **prerequisites**, and **current state**. |
| **Outputs** | **Directive** (or mapping to existing directive/work), **plan update**, or **rejection** with reason. |

**System must reject**

- Direct **human → non-Architect agent** execution on governed paths  
- **Unscoped** work (no project/directive context)  
- **Invalid state transitions** (§7)  

---

## 5. Input normalization model

**Accept:** markdown, PDF, plain text, chat messages, code snippets, uploaded documents (formats expanded under implementation — blueprint requires **extensibility**).

**Pipeline**

1. **Store** raw artifact (auditable).  
2. **Extract** content (format-specific extractors).  
3. **Normalize** into structured representation (schema owned by LLD/API).  
4. **Pass** to Architect for interpretation.  

**Human is not responsible for formatting** — normalization is a **system responsibility**.

---

## 6. Shared memory / RAG model

| Rule | Detail |
|------|--------|
| **Isolation** | Each project has its **own context namespace**. **Context isolation is mandatory.** |
| **Architecture** | **Single context engine** (multi-tenant), **partitioned by `project_id`**. |
| **Queries** | **All retrieval queries require `project_id`.** |
| **Forbidden** | **No cross-project retrieval**; **no global fallback** that mixes corpora. |

**Context types**

- **Conversation memory** — shared thread + decisions surfaced in chat  
- **Project memory (RAG)** — indexed docs/code/artifacts  
- **Decision memory** — approved facts / signed architecture / immutable decisions  
- **Temporary working context** — short-lived scratch with explicit TTL/policy  

Structured store (Postgres) remains **source of truth** for entities; vectors are **derived** for recall.

---

## 7. State machine

All governed work follows **explicit states**. Transitions are **validated**, **logged**, and **non-skippable** without audited waiver policy.

**Example lifecycle** (representative — exact enum mapping in **`APP_LLD_001`** / DB):

```text
DRAFT → ISSUED → ACKNOWLEDGED → PLANNING → PLAN_APPROVED
→ STRUCTURE_APPROVED → PREREQS_APPROVED → BUILDING
→ PROOF_RETURNED → REVIEW → ACCEPTED | REJECTED
→ BUG_CHECK → SIGNOFF → CLOSED
```

| Rule | Enforcement |
|------|-------------|
| No transition without validation | Backend **StateTransitionService** (future slices) + API guards |
| No skipping steps | Illegal transitions **409** unless **WAIVED** per policy + audit |
| All transitions logged | **`state_transition_log`** + **`AuditEventType.STATE_TRANSITION`** (pattern per **`STATE_001`**) |

**Orthogonal:** **BLOCKED** — stop state with recovery path; not a substitute for skipping lifecycle.

---

## 8. Project structure rules

| Step | Action |
|------|--------|
| 1 | Classify **project type** |
| 2 | Generate **architecture** |
| 3 | Derive **canonical structure** |
| 4 | Operator approves **both** |
| 5 | **Scaffold** |
| 6 | **Build** |

| Rule | Detail |
|------|--------|
| Boundaries | **No files outside approved structure** without approval |
| Changes | Structural changes require **approval** + audit |
| Scratch | **Scratch mode** allowed **only** when explicitly enabled and **audited** |

---

## 9. Environment governance

| Mandatory | Detail |
|-----------|--------|
| **Container-first** | **Dockerfile** + **compose** (or equivalent) for runnable system |
| **Local env in container** | **venv** / **uv** / **npm + lockfile** — **no global deps as source of truth** |
| **`.env.example`** | Required committed template; **`.env`** never committed |
| **Reproducibility** | **`docker compose up --build`** (or documented single command) yields consistent runtime |

| Rules | |
|-------|--|
| No **host-only** primary runtime | |
| **Portable** and **scalable-by-design** (config-driven endpoints) | |

---

## 10. Model cadre readiness

| Requirement | Detail |
|-------------|--------|
| Mapping | Each **agent role** maps to a **model profile** |
| Availability | Required models must be **detected** before governed execution |
| Block | **Block execution** if required models **missing** (unless explicit **DEGRADED** policy + user acknowledgment) |
| Remediation | **Install commands / guidance** — **no silent** fallback to unknown or undisclosed models |
| External | External inference **only** via governed router path (**100R / FIX005**) — **no ad hoc vendor calls** |

---

## 11. Patch / apply governance

**Mandatory path**

```text
edit → patch propose → validation → proof → review → accept | reject → apply
```

| Rule | Detail |
|------|--------|
| Protected branches | **No direct commits** to protected branches through governed flow |
| Application | **Backend-controlled** patch application |
| Locks | **Lock required** for apply / mutation validation paths |

---

## 12. Proof / bug-check loop

| Step | Actor / system |
|------|----------------|
| 1 | **Proof** generated |
| 2 | **Reviewer** evaluates |
| 3 | If **accepted** → enter **bug-check** phase (**not** silently skipped) |
| 4 | **QA/Test** runs validation |
| 5 | **Debugger** resolves failures if needed |
| 6 | **Sign-off** required before **closure** |

**UI must show** whether bug-check **ran**, **passed**, **failed**, or **WAIVED** (with reason).

---

## 13. API gaps (inventory)

Prefix: **`/api`** + **`/v1/...`** as deployed (respect **`TRIDENT_BASE_PATH`**). Below: **today’s spine** vs **blueprint-required** surface.

### 13.1 Project management

| Capability | Status |
|------------|--------|
| Projects CRUD / settings | **Missing** (directives reference `project_id`; no full project API in control plane) |
| Workspace ↔ project listing | **Partial** — implicit via DB; **Missing** dedicated REST |

### 13.2 Membership / invites

| Capability | Status |
|------------|--------|
| Members, roles (OWNER/ADMIN/…) | **Missing** |
| Invites | **Missing** |

### 13.3 Intake / normalization

| Capability | Status |
|------------|--------|
| Artifact upload + extract pipeline | **Missing** |
| `#architect` trigger binding | **Missing** (chat stub exists — **existing** partial: **`POST /v1/ide/chat`**) |

### 13.4 Directive lifecycle

| Capability | Status |
|------------|--------|
| Create/list/get directive | **Existing:** `POST/GET /v1/directives`, `GET /v1/directives/{id}` |
| Run workflow | **Existing:** `POST /v1/directives/{id}/workflow/run` |
| Lifecycle transitions API | **Missing** (unified transition / phase endpoints) |

### 13.5 State transitions / gates

| Capability | Status |
|------------|--------|
| Execution UI aggregate | **Missing** (`execution-ui-state`) |
| Project gates (PLAN/STRUCTURE/PREREQS) | **Partial** — **`project_gates`** table (**STATE_001**); **Missing** REST |
| Prerequisite checklist | **Missing** |

### 13.6 Context / RAG

| Capability | Status |
|------------|--------|
| Memory read by project/directive | **Existing:** `GET /v1/memory/project/{id}`, `GET /v1/memory/directive/{id}` |
| Memory write | **Existing:** `POST /v1/memory/write` |
| Vector retry | **Existing:** `POST /v1/memory/retry-vector-index` |
| Scoped hybrid `rag/query`, ingest, reindex, stale-report | **Missing** |

### 13.7 Lock management

| Capability | Status |
|------------|--------|
| Acquire/release/active/heartbeat/simulated-mutation | **Existing** under **`/v1/locks/*`** |
| Force-release | **Existing:** `POST /v1/locks/force-release` |

### 13.8 Patch workflow

| Capability | Status |
|------------|--------|
| Propose/reject/apply-complete | **Existing:** **`/v1/patches/*`** |

### 13.9 Proof / review

| Capability | Status |
|------------|--------|
| IDE proof summary stub | **Existing:** `GET /v1/ide/proof-summary/{directive_id}` |
| Proof package + ACCEPT/REJECT decision API | **Missing** |

### 13.10 Collaboration (comments / ledger)

| Capability | Status |
|------------|--------|
| Shared thread API | **Missing** |
| Comment / reaction model | **Missing** (beyond memory — **Missing**) |

### 13.11 Model readiness

| Capability | Status |
|------------|--------|
| Model router status | **Existing:** `GET /v1/system/model-router-status` |
| Full model cadre status/refresh/assign | **Missing** |

### 13.12 System health

| Capability | Status |
|------------|--------|
| Health / ready | **Existing:** `/health`, `/ready` |
| Version | **Existing:** `/version` |
| Schema status | **Existing:** `GET /v1/system/schema-status` |

### 13.13 Other existing (orchestration)

| Area | Status |
|------|--------|
| Nike events | **Existing:** `POST/GET /v1/nike/events` |
| MCP classify/execute | **Existing:** `POST /v1/mcp/classify`, `POST /v1/mcp/execute` |
| Subsystem router | **Existing:** `POST /v1/router/route` |
| IDE chat/action/status | **Existing:** `POST /v1/ide/chat`, `POST /v1/ide/action`, `GET /v1/ide/status/{directive_id}` |

### 13.14 Deprecated

| Item | Note |
|------|------|
| *None formally marked deprecated in this blueprint pass* | Future directives must label deprecations in OpenAPI/changelog |

---

## 14. Implementation phases

| Phase | Scope |
|-------|--------|
| **Phase 1** | Single-user **minimal** path: **state engine** enforcement wiring, **Architect intake** (`#architect`), **basic** extension/UI surfaces backed by aggregates |
| **Phase 2** | **Multi-user** collaboration, **shared chat** API, **membership** & roles |
| **Phase 3** | **RAG/context engine** completion (hybrid retrieval, ingest, staleness), **model routing** cadre integration |
| **Phase 4** | **Advanced orchestration**, performance, polish, observability |

Phases align with **`APP_LLD_001`** epic sequencing; **gates are not relaxed** in early phases — scope is **surface area**, not rules.

---

## 15. Acceptance criteria

The system must demonstrate:

| # | Criterion |
|---|-----------|
| 1 | Backend can **reconstruct full project state** from durable stores |
| 2 | **Multiple users** see **identical** authoritative state for the same project |
| 3 | **No cross-project context leakage** in retrieval or chat |
| 4 | Governed actions go through **Architect** or **explicit allowed paths** (locks, patches, workflow) |
| 5 | **State machine cannot be bypassed** without audited waiver |
| 6 | **Patches** require **review/approval** before apply |
| 7 | **Environment** reproducible per §9 |
| 8 | **Model readiness** enforced before execution |
| 9 | **Input normalization** works across declared formats |
| 10 | **Collaboration** is consistent; conflicts resolved via ledger/state, not client divergence |

---

## RETURN — `APP_BLUEPRINT_001_UNIFIED_REWRITE`

| Field | Value |
|--------|--------|
| **Directive** | `APP_BLUEPRINT_001_UNIFIED_REWRITE` |
| **Status** | **READY** — unified blueprint **complete** for engineering alignment; **BLOCKED** only if program rejects (no technical blocker stated) |
| **Sections completed** | §§1–15 (product model through acceptance criteria + API inventory) |
| **Open gaps** | APIs in §13 marked **Missing**; membership; shared chat; RAG query surface; proof decisions; execution-ui-state; intake pipeline |
| **Conflicts** | Prior **addendum-only** file structure **retired** — use **this document** only; reconcile **`APP_LLD_001`** epic wording with **`#architect`** and **human roles** in next LLD revision if needed |
| **Risks** | Client-side state drift if aggregates lag; normalization quality on PDFs; multi-tenant RAG misconfiguration; waiver creep on gates |
| **Estimated work** | Align with **`APP_LLD_001` §11** — full program **~46–74** eng-weeks parallelized; **Phase 1** on order of **~8–14** eng-weeks depending on team |

---

**END — APP_BLUEPRINT_001 (Unified)**
