# APP_IMPLEMENTATION_DESIGN_001_REVIEW — Design validation vs blueprint

**Directive:** `APP_IMPLEMENTATION_DESIGN_001_REVIEW`  
**Status:** **ISSUED** (review **READY** — §RETURN)  
**Inputs:** `trident/docs/APP_BLUEPRINT_001.md`, `trident/docs/APP_IMPLEMENTATION_DESIGN_001.md`  
**Constraint:** **No code changes** in this directive — validation and build-authorization input only.

---

## 1. Design validation (blueprint rules → design enforcement)

| Blueprint rule | Enforced in design? | Evidence |
|----------------|---------------------|----------|
| Backend authoritative; no durable client-only state | **Yes** | §1 control plane + §9 `execution-ui-state` server-computed `actions_allowed`; extension client-only. |
| Single shared chat per project | **Yes** | §2 `conversation_messages` + `GET/POST .../conversation`; `thread_id = project_id` v1. |
| `#architect` triggers Architect intake | **Yes** | §1.4 + §6 flow + §3 API **`/ide/chat` changed** to route `#architect` to intake; message `tags` / parse flag. |
| Actionable execution via Architect path | **Partial — design complete, code pending** | §6 Nike `ARCHITECT_INTAKE`; directives created **only** via state engine. **Gap:** **`POST /v1/mcp/execute`** and **`POST /v1/router/route`** must be **explicitly** governed in implementation (reject unscoped / non–Architect-approved agent execution) — see §2 gaps. |
| Invalid state transitions rejected | **Yes (design)** | §4 matrix + **409** + single writer `StateTransitionService`; LangGraph/Nike refactors specified. **Runtime:** depends on **STATE_002** implementation. |
| Project-scoped RAG; no cross-project; no global mixed corpus | **Yes** | §5 mandatory `project_id` on API/SQL/Chroma `where`; CI test requirement stated. |
| Patch governed flow; lock for apply | **Yes** | §8 + §3 patch apply **gate preflight**; §7 lock granularity + apply path via `simulated-mutation`. |
| Environment / model readiness gates | **Partial** | §4 `*` precondition “gates + model readiness”; §3 `model-cadre/status` **new**. **Prerequisite checklist** merge into `project_gates` **PREREQS** — design implies; **explicit prereq item table** not in IMPLEMENTATION_DESIGN §2 — **flag** (resolve in build: extend PREREQS gate payload vs separate table per **STATE_001** follow-on). |

### 1.1 Explicit confirmations

| Item | Verdict |
|------|---------|
| **`#architect` intake enforcement path** | **Confirmed in design:** `conversation_messages` → parse tag → `normalized_documents` / Nike → Architect worker → **state engine** only for directive mutation. **Implementation must** reject chat lines that attempt to invoke Engineer/Reviewer MCP without prior Architect-bound directive context (exact HTTP/MCP error code in first build ticket). |
| **Project-scoped context guarantees** | **Confirmed:** triple layer (API scope assert, SQL `WHERE project_id`, Chroma `where` metadata). |
| **State machine cannot be bypassed** | **Confirmed in design** via single mutation path + transaction + log. **Residual bypass risk:** direct DB admin, unrefactored `update_directive_status` in graph — **eliminated by implementation checklist** (grep CI + refactor before “done”). |
| **Patch/apply governed flow** | **Confirmed:** propose → validate lock + git → proof; no apply without path through existing mutation stack. |

---

## 2. Gap resolution (no “TBD” on core systems)

| Gap | Resolution for build |
|-----|---------------------|
| **Prerequisite checklist vs `project_gates` only** | **BLOCK for ambiguity removed:** Implement **either** (a) `prerequisite_items` child table keyed by `project_id` with aggregate rolled into `gates` API, **or** (b) JSONB `gates.detail` on project — pick **(a)** for audit/query clarity. Document in first schema ticket; **not optional**. |
| **MCP / subsystem router: human → agent bypass** | **Resolved rule:** Any **`MCP_EXECUTE`** or **`router/route`** that starts governed work requires **`directive_id`** + **`task_id`** in approved state **and** ledger owner consistent with Architect-outlined work; otherwise **403** `architect_gate_required`. Spec lives in implementation directive for **100F/100G hardening** slice — **design accepts** this as mandatory middleware. |
| **Full directive transition matrix “illustrative”** | **Resolved:** Before **STATE_002** merge, publish **complete** matrix appendix (all `DirectiveStatus` × allowed next) matching blueprint §7 path including **STRUCTURE_APPROVED / PREREQS_APPROVED** as **gate-backed** transitions into **BUILDING** (not necessarily separate enum values if gates are authoritative — **must be one coherent model**). |
| **Blueprint context types (decision / temp)** | **Resolved:** Use **`memory_kind`** enum values: `CONVERSATION`, `PROJECT_RAG`, `DECISION`, `TEMP_WORKING` + TTL in `payload_json`. |
| **Auth “existing largely unchecked”** | **Resolved:** **First epic** in any build wave is **auth + membership middleware**; no “new” project APIs ship without it. |

**No remaining “to be decided later” for:** isolation, state writer discipline, lock semantics, patch apply chain, `#architect` routing intent — all bound by decisions above.

---

## 3. Cross-system consistency check

| Interface | Assessment |
|-----------|------------|
| **State engine ↔ API ↔ UI** | **Consistent:** `execution-ui-state` aggregates directive + ledger + gates + `actions_allowed`; transitions via **`POST .../transition`** + service; UI polls — aligns with blueprint thin client. |
| **Context ↔ intake ↔ Architect** | **Consistent:** `normalized_documents` → `ArchitectInputEnvelope` → directive proposal; RAG ingest separate path but same `project_id`. |
| **Locks ↔ patch ↔ collaboration** | **Mostly consistent:** file-path locks match patch `file_path`; **membership** on lock APIs required in design §3 — aligns with blueprint collaboration. **Watch:** **parallel attempts** on **same directive** different files — allowed; same file — **409** — deterministic. |
| **Lifecycle: blueprint §7 vs design §4 matrix** | **Clarification required in implementation (not a redesign):** Blueprint lists **STRUCTURE_APPROVED** and **PREREQS_APPROVED** as **lifecycle words**; design places **PLAN / STRUCTURE / PREREQS** in **`project_gates`**, while directive **`status`** may jump **PLAN_APPROVED → BUILDING**. **Resolution:** Treat **STRUCTURE_APPROVED** and **PREREQS_APPROVED** as **gate satisfactions** + optional **`directive_phase`** field updates, **not** duplicate string values in `directives.status` unless STATE_002 chooses to mirror — **either is valid** if **execution-ui-state** exposes a **single** user-visible phase model. **Flag as doc-only alignment** task in sprint 0. |

---

## 4. Failure mode validation (deterministic outcomes)

| Scenario | Expected outcome (design-backed) |
|----------|-----------------------------------|
| **Concurrent transition requests** | First wins **FOR UPDATE**; second **409** `stale_state` or `transition_conflict` with `current_state` echo. |
| **Concurrent workflow runs** | Idempotency / **409** `workflow_active` per design §11. |
| **Lock conflict** | Second acquire **409** with current holder + `lock_id`. |
| **Heartbeat miss** | Stale lock path per FIX 003; edit/save blocked; deterministic recovery via release/takeover policy. |
| **Partial failure mid-transaction** | Single DB transaction rollback — no half-written status without log (§4.3). |
| **Context leakage attempt** | API rejects mismatched JWT `project_id`; query layer rejects missing filter — **empty result**, never silent merge. |
| **Model unavailable** | `actions_allowed.start_build=false`; **409** on gated transitions if policy requires READY models; remediation surfaced via cadre status. |

---

## 5. Build readiness decision

### **READY_FOR_IMPLEMENTATION (design-validated)**

**Rationale:** `APP_IMPLEMENTATION_DESIGN_001` **covers** all blueprint **core systems** with **enforceable** bindings; remaining items are **specified resolutions** in §2 above, not open design voids.

**Controlled authorization:** First merged **implementation directives** must **sequence:** (1) auth/membership, (2) **STATE_002** `StateTransitionService` + full matrix appendix, (3) **execution-ui-state**, (4) conversation + `#architect` wiring, (5) MCP/router guard, (6) RAG query route + isolation tests.

**Not production-complete** until those slices ship — but **design review does not BLOCK** starting implementation under that order.

---

## 6. Final critical path confirmation

| Epic order (from IMPLEMENTATION_DESIGN §10) | Hidden dependency found? |
|---------------------------------------------|---------------------------|
| Auth + membership → State engine → execution-ui-state → conversation/intake → RAG → proof/validation | **Yes — implicit:** **OpenAPI + JWT claims** must include **`project_id` scope** before RAG query ship — already sequenced after auth. |
| **Nike/LangGraph refactor** to state service | Depends on **STATE_002** — must not parallelize **before** service skeleton merges or risk dual writers. |

**Critical path duration:** **IMPLEMENTATION_DESIGN §12** (~12–16 weeks single-threaded equiv.) remains **credible** if **STATE_002** lands early; **+2–3 weeks** if MCP/router guard scope expands.

**Adjustment:** Add explicit milestone **“MCP/router guard”** on critical path **before** exposing **BUILDING** transitions to external automation.

---

## RETURN — `APP_IMPLEMENTATION_DESIGN_001_REVIEW`

| Field | Value |
|--------|--------|
| **Directive** | `APP_IMPLEMENTATION_DESIGN_001_REVIEW` |
| **Status** | **READY** |
| **Validation summary** | Blueprint rules **mapped** to enforcement points; **design READY_FOR_IMPLEMENTATION** with **sequenced** implementation prerequisites (§5). |
| **Gaps** | Prereq storage shape; full transition matrix appendix; MCP/router **Architect gate** middleware spec ticket; **directive_phase** vs **gate** naming alignment for UX — **all resolved** in §2 for build (no lingering TBD). |
| **Inconsistencies** | STRUCTURE/PREREQS as **gates** vs **status** words — **resolved** by single visible phase in UI aggregate (§3). |
| **Failure modes** | §4 — deterministic **409**/rollback/empty-retrieval outcomes. |
| **Critical path confirmation** | §6 — auth first; STATE_002 before graph refactor; MCP guard on path to BUILDING. |
| **Build readiness** | **READY_FOR_IMPLEMENTATION** (controlled — per §5 ordering). |

---

**END REVIEW**
