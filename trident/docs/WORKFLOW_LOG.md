# TRIDENT — Unified workflow log (mandatory)

**Authority:** Cumulative, append-only audit record for directive execution. A reviewer must be able to reconstruct system evolution from this file.

**Rules:** Do not rewrite prior sections. Failed attempts and gate outcomes stay visible. Directive work must land with a matching append to this log.

---

## Directive: WORKFLOW_LOG_INIT

**Status:** PASS

### Plan

Establish `trident/docs/WORKFLOW_LOG.md` as the single unified workflow log; backfill **100A → 100F** at summary level for continuity; align engineering receipts with program gate decisions already recorded in thread / prior audit notes.

### Plan Decision

**ACCEPTED** — program mandated file path, section schema, append-only discipline, and summary backfill requirement.

### Build Summary

Created this log file with standardized sections per program specification.

### Files Changed

- `trident/docs/WORKFLOW_LOG.md` (new)

### Commands Run

`git log --oneline` (scope: `trident/backend`, `trident/docs`) to anchor representative SHAs for backfill.

### Tests

N/A (documentation-only init).

### Proof

Repo HEAD at authoring: `4482f2c`; backfill SHAs cross-checked against git history for 100A–100C and recent 100D–100E chain.

### Gate Decision

**PASS** — mandatory log path and format satisfied; backfill present through **100F (current)**.

### Final State

Unified workflow logging is enforceable: future directives append new `## Directive: <ID>` blocks below.

### Known Gaps

Summary backfill is not a full forensic reconstruction; exact historical dates per gate may be refined via future **correction append** rows if records diverge.

### Unlock

All subsequent directives must append here; **100F** build remains gated on explicit plan acknowledgment.

---

## Directive: 100A

**Status:** PASS

### Plan

Implement repository + runtime skeleton per `TRIDENT_IMPLEMENTATION_DIRECTIVE_100A_REPOSITORY_RUNTIME_SKELETON.md` (layout, health/config placeholders, validation proof path, `/trident` deploy alignment).

### Plan Decision

**ACCEPTED** — skeleton scope only (no agent logic, memory, MCP, router, UI business logic, git automation).

### Build Summary

Initial `trident/` tree (backend, frontend, worker, docker, docs, `runtime/proof/`), compose baseline, base-path aware routing and clawbot deployment documentation.

### Files Changed

Summary: `trident/backend/**`, `trident/docker-compose.yml`, `trident/docs/**`, `trident/runtime/**`; representative commits `fb109eb`, `ed1b6f9`, `c52bd01`, `23930fe`.

### Commands Run

`pytest` (includes base-path `/trident` tests); `docker compose config` where environment allowed — per `trident/runtime/proof/100A_PROOF_NOTES.txt`.

### Tests

**PASS** — pytest per proof notes; full compose up/curl/restart not run in agent/CI environment (documented).

### Proof

`trident/runtime/proof/100A_PROOF_NOTES.txt`; commits above.

### Gate Decision

**PASS** — skeleton + documented deploy target; explicit caveat on Docker daemon not available in some validation environments.

### Final State

Runtime skeleton and deployment checklist baseline; unlocks schema work (**100B**).

### Known Gaps

Docker runtime proof left to environments with Docker daemon (per 100A proof notes).

### Unlock

**100B** enabled.

---

## Directive: 100B

**Status:** PASS

### Plan

Implement schema models, persistence, and migrations for core records per `TRIDENT_IMPLEMENTATION_DIRECTIVE_100B_SCHEMA_PERSISTENCE_FOUNDATION.md` (directives, ledger, graph state, handoffs, proofs, audits, workspace/user placeholders, file-lock placeholder).

### Plan Decision

**ACCEPTED** — persistence foundation only (no LangGraph execution semantics beyond storage, no memory/MCP/router/UI).

### Build Summary

SQLAlchemy models, repositories, Alembic baseline migration `100b001_initial_schema.py`, audited directive pathway scaffolding.

### Files Changed

`trident/backend/app/models/**`, `trident/backend/app/repositories/**`, `trident/backend/alembic/versions/100b001_initial_schema.py`, related API/tests; anchor commit `9b91430`.

### Commands Run

Alembic revision application in dev/validation contexts; pytest for persistence layer (per implementation).

### Tests

**PASS** — foundation covered by project test suite at time of merge (summary).

### Proof

Commit `9b91430`; migration `100b001`.

### Gate Decision

**PASS** — schema + migration foundation merged.

### Final State

Durable persistence for ledger/graph/proof/audit primitives; unlocks LangGraph spine (**100C**).

### Known Gaps

None recorded at summary level.

### Unlock

**100C** enabled.

---

## Directive: 100C

**Status:** PASS

### Plan

Implement LangGraph workflow spine per `TRIDENT_IMPLEMENTATION_DIRECTIVE_100C_LANGGRAPH_SPINE.md` (Architect → Engineer → Reviewer → Docs → Close, rejection loop; persistence via **100B**).

### Plan Decision

**ACCEPTED** — all multi-agent execution routed through LangGraph nodes only.

### Build Summary

`StateGraph` spine, persistence hooks, API entry for directive workflow execution, ledger/audit writes aligned to graph transitions.

### Files Changed

`trident/backend/app/workflow/**`, `trident/backend/app/api/v1/directives.py`, `trident/backend/tests/test_langgraph_spine.py`; anchor commit `fdec2b8`.

### Commands Run

`pytest` including `tests/test_langgraph_spine.py`.

### Tests

**PASS** — LangGraph spine tests green at merge (summary).

### Proof

Commit `fdec2b8`; test module `test_langgraph_spine.py`.

### Gate Decision

**PASS** — enforced graph execution path present.

### Final State

Governed multi-agent execution shell; unlocks memory system (**100D**).

### Known Gaps

Placeholder behaviors in some nodes per directive (no full code mutation stack).

### Unlock

**100D** enabled.

---

## Directive: 100D

**Status:** PASS

### Plan

Implement memory system per `TRIDENT_IMPLEMENTATION_DIRECTIVE_100D_MEMORY_SYSTEM.md` (Chroma integration, graph-governed writes, scoped reads, validation).

### Plan Decision

**ACCEPTED** — memory scope only; sequencing later locked as **100D → FIX 004 → 100E** before **100E** build.

### Build Summary

Memory writer/read paths, Chroma integration (PersistentClient local / HttpClient Docker), MiniLM embedding path, migration support for memory entries.

### Files Changed

Memory modules, `trident/backend/tests/test_memory_100d.py`, `trident/backend/alembic/versions/100d003_memory_entries.py`; anchor commit `b0113bf`.

### Commands Run

`pytest tests/test_memory_100d.py` local and clawbot (`TRIDENT_CHROMA_HOST=trident-chroma`); compose services per deployment docs.

### Tests

**PASS** — 5/5 memory tests local PersistentClient; 5/5 clawbot HttpClient after stable embedding download; environmental ONNX fetch interruption treated as re-run, not code FAIL.

### Proof

Commit `b0113bf`; structured proof summarized in prior audit (`DIRECTIVE_WORKFLOW_LOG.md` row W-003); clawbot + local receipts per thread.

### Gate Decision

**PASS** — program **ACCEPTED** structured proof (local + clawbot).

### Final State

Memory subsystem operational enough to gate **FIX 004** (transaction / vector consistency) before **100E**.

### Known Gaps

Embedding download can fail on flaky networks (operational re-run).

### Unlock

**FIX 004** (program gate) then **100E**.

---

## Directive: 100E

**Status:** PASS

### Plan

Implement Git read-only validation and strict file locks with simulated mutation proof per `TRIDENT_IMPLEMENTATION_DIRECTIVE_100E_GIT_FILE_LOCK.md`, after **FIX 004** closure.

### Plan Decision

**ACCEPTED** — lock lifecycle, conflict handling, audits, containerized proof on clawbot.

### Build Summary

File lock model + constraints, git path safety / read-only git, lock API routes, `clawbot_100e_proof.py`, API image includes `git` + tests for compose-exec pytest.

### Files Changed

`trident/backend/app/locks/**`, `trident/backend/app/git/**`, API v1 locks, `trident/backend/clawbot_100e_proof.py`, `trident/backend/tests/test_locks_100e.py`, `trident/backend/alembic/versions/100e001_file_lock_git_constraints.py`; commits `c70c7ce`, `4482f2c`.

### Commands Run

`docker compose` rebuild; `alembic upgrade head`; Postgres proof script (acquire / conflict / release / re-acquire / simulated mutation); **restart `trident-api`**; `pytest tests/test_locks_100e.py` (8 passed in container).

### Tests

**PASS** — 8 passed in container per program sign-off.

### Proof

HEAD proof bundle `4482f2c`; Alembic `100e001`; audit events `GIT_STATUS_CHECKED` / `DIFF_GENERATED`; prior audit row W-005.

### Gate Decision

**PASS** — program **ACCEPTED** full proof list (lock/conflict/release/restart/read-only git/mutation/proofs/audits/tests).

### Final State

Governed file locking + git evidence path validated on clawbot; unlocks downstream directives including **100F** implementation once planned.

### Known Gaps

Non-blocking: orphan `trident-vector` noted during clawbot validation.

### Unlock

**100F** build (pending plan acknowledgment).

---

## Directive: 100F

**Status:** BLOCKED

### Plan

Implement MCP execution layer per `TRIDENT_IMPLEMENTATION_DIRECTIVE_100F_MCP_EXECUTION.md` after governed Read → Plan → Build sequence.

### Plan Decision

**CHANGES REQUESTED / PENDING** — engineering submitted **Step 1 Read** + **Step 2 Plan**; explicit architect acknowledgment of plan **not yet recorded**; **no build** authorized until then.

### Build Summary

N/A — implementation not started (blocked on plan gate).

### Files Changed

N/A for implementation (planning artifacts may exist only in chat / directive workspace until build).

### Commands Run

N/A for build.

### Tests

N/A.

### Proof

N/A — planning delivery only; prior audit row W-001 **PENDING**.

### Gate Decision

**CONDITIONAL** — **BLOCKED** until plan acknowledgment; Step 3 Build not authorized; no merge closure without proof block.

### Final State

No MCP execution layer merged; system remains without governed MCP command path until unblock.

### Known Gaps

Full MCP adapters (SSH stub only per directive), approval UX, and integration with LangGraph nodes remain future work post-unblock.

### Unlock

Next: architect **ACCEPTED** plan → engineering **Build** → proof → **PASS** gate → append completion section or new status block (append-only).

---

## Directive: 100F — Step 3 Build (accepted plan)

**Status:** PASS

### Plan

Implement MCP execution API (`POST /api/v1/mcp/classify`, `POST /api/v1/mcp/execute`) with simulated adapters only, HIGH explicit-approval gate, `ProofObject(EXECUTION_LOG)` receipts, and audits (`MCP_EXECUTION_REQUESTED`, `MCP_EXECUTION_COMPLETED`, `MCP_EXECUTION_REJECTED`, `MCP_EXECUTION_FAILED` available).

### Plan Decision

**ACCEPTED** — program authorization to proceed with Step 3 Build; simulated execution only; no router/memory/Nike/UI/file-git mutation.

### Build Summary

New `app/mcp/` package (classifier, validator, service, audit logger, FastAPI `mcp_router`, local + SSH **stub** adapters). Execute path persists EXECUTION_LOG proofs (including HIGH rejection receipts). DB session commits on `HTTPException` so rejection audits/receipts survive 403 responses.

### Files Changed

`trident/backend/app/mcp/**`, `trident/backend/app/schemas/mcp.py`, `trident/backend/app/api/routes.py`, `trident/backend/app/db/session.py`, `trident/backend/tests/conftest.py`, `trident/backend/tests/test_mcp_100f.py`, `trident/backend/clawbot_100f_proof.py`, `trident/backend/Dockerfile`, `trident/backend/app/models/enums.py`.

### Commands Run

`python3 -m pytest` — full suite **61 passed** (includes `tests/test_mcp_100f.py`).

### Tests

**PASS** — classification; LOW auto path; HIGH 403 without `explicitly_approved`; HIGH success with flag; ssh_stub adapter; invalid target; package contains no `subprocess` / `os.system`.

### Proof

API base `/api/v1/mcp/`; required context fields enforced; clawbot script `clawbot_100f_proof.py` (DB seed + httpx against live API). Git: merge commit titled **`feat(100F): MCP classify/execute API with simulated adapters`** (verify with `git log -1 --oneline`).

### Gate Decision

**PASS** — meets simulated-only execution, HIGH gate, receipt + audit visibility requirements.

### Final State

MCP classify/execute available for governed intent capture; unlocks **100G Router** per directive manifest (not implemented here).

### Known Gaps

SSH adapter remains stub; MEDIUM “optional approval” not modeled as separate token (execute always re-classifies); LangGraph node wiring to MCP API not in scope.

### Unlock

**100G** (Router) authorized per parent directive manifest when program issues next gate.

---

## Directive: 100F_FINAL — Clawbot HTTP + DB + restart

**Status:** PENDING (operator must run on clawbot; see script output for PASS/FAIL)

### Plan

Final validation: all MCP calls over HTTP to `http://localhost:8000/trident/api/v1/mcp/...` (with `TRIDENT_BASE_PATH=/trident`); DB receipt counts; `docker compose restart trident-api` then re-run LOW execute.

### Plan Decision

**ACCEPTED** — program requires clawbot proof before **100G**; no router work.

### Build Summary

- `clawbot_100f_final_validation.py` — full phase: DB bootstrap directive, HTTP classify/LOW/HIGH-reject/HIGH-ok, assert 3× `EXECUTION_LOG` proofs, 3× `MCP_EXECUTION_REQUESTED`, 2× `MCP_EXECUTION_COMPLETED`, 1× `MCP_EXECUTION_REJECTED`.
- `--phase restart-low` with `TRIDENT_100F_DIRECTIVE_ID` / `TRIDENT_100F_TASK_ID` after API restart.
- `agent_role` accepted case-insensitively (e.g. `engineer` → `ENGINEER`) for architect curl examples.

### Files Changed

`trident/backend/clawbot_100f_final_validation.py`, `trident/backend/app/mcp/mcp_validator.py`, `trident/backend/tests/test_mcp_100f.py`, `trident/backend/Dockerfile`.

### Commands Run (CI / dev)

`python3 -m pytest` — full suite **62 passed**.

### Clawbot (operator)

```bash
ssh jmiller@clawbot.a51.corp
cd ~/code_projects/trident/trident/trident
git pull origin main
docker compose down
docker compose up -d --build
docker compose exec trident-api python -m alembic current
docker compose exec trident-api python clawbot_100f_final_validation.py
docker compose restart trident-api
# then use printed export + restart-low command
```

Curl samples (replace UUIDs from script output): `POST .../trident/api/v1/mcp/classify` and `/execute` as in program message.

### Gate Decision

**PENDING** until clawbot run shows `100f_final_validation_ok=1` and `100f_final_restart_low_ok=1`.

### Final State

When PASS: **100F** closed for deployment target; **100G** still blocked until program explicitly enables.

### Known Gaps

Local engineering host may lack Docker/SSH to clawbot; final sign-off is on **clawbot** only.

---

## Directive: 100F_FINAL — Clawbot execution record

**Status:** PASS

### Proof (clawbot `2026-04-30`)

- **Git:** `7f3153c` on clawbot workspace after `git pull`.
- **Alembic:** `100e001 (head)`.
- **HTTP base:** `http://127.0.0.1:8000/trident/api/v1` (compose `TRIDENT_BASE_PATH=/trident`).
- **Full validation:** `100f_final_validation_ok=1`; classify **LOW**; LOW execute **200**; HIGH reject **403** `high_risk_not_approved` proof `1712d96d-7310-46c5-b6a6-2448e94dfaa7`; HIGH approved **200**; DB `proof_objects_exec_log_count=3`, `mcp_audit_requested=3 completed=2 rejected=1`.
- **Restart LOW:** after `docker compose restart trident-api`, `restart_low_execute_status=200`, proof `150b95ec-132a-4123-b4ed-f80923f2c4d0`, `100f_final_restart_low_ok=1`.
- **Directive/task IDs (proof run):** `6dcf3ddd-d393-4871-ba5e-c220e2e68821` / `93712920-db08-4fe8-ab2f-ff29c5307a06`.

### Gate Decision

**PASS** — clawbot validation script green end-to-end including persistence after API restart.

---

## Directive: 100F_FINAL — Program acceptance

**Status:** PASS **(ACCEPTED)**

### Gate Decision

Program **ACCEPTED** **100F_FINAL** as **PASS** (clawbot evidence recorded above). **100F** is formally closed. **100G** subsystem-router **implementation** remains blocked until doc conflict resolution is **ACCEPTED** and plan gate clears (see **DOC_100G_CONFLICT_RESOLUTION** below).

---

## Directive: DOC_100G_CONFLICT_RESOLUTION

**Status:** PASS (documentation delivered — program acceptance on file set optional)

### Plan

Separate **subsystem work-request router (100G)** from **model router / LLM escalation (100R)**; relocate legacy LLM **100G** text to **100R**; refresh Manifest + Master Execution Guide + Playbook + **000G** + FIX **005** references.

### Plan Decision

**Engineering complete** — awaiting explicit program **ACCEPTED** if required by governance.

### Files Changed

See git commit; includes new **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100R_MODEL_ROUTER_LOCAL_FIRST.md`**, rewritten **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100G_ROUTER.md`**, **`TRIDENT_DOCUMENT_MANIFEST_v1_0.md`**, **`TRIDENT_MASTER_EXECUTION_GUIDE_v1_1.md`** / **v1_0**, Playbooks **v1_0**/**v1_1**, **`TRIDENT_DIRECTIVE_000G_ROUTER_POLICY.md`**, **FIX 005**, cross-references in **100F**/**100H**/**100I**/**100N**.

### Gate Decision

**PASS** (doc-only) — conflict explicitly documented; **100G build** still blocked until plan acceptance for implementation (unchanged enforcement).

### Known Gaps

**100R** schedule is program-defined; **v1_0** Master Guide omits **100O** ordering detail — **v1.1** remains authoritative.

---

## Directive: 100G — Router (orchestration layer)

**Status:** PLANNING

### Plan (Step 1 — Read)

- **Issued:** program message — control/orchestration router; **decides only**; no execution, subprocess, MCP bypass, file or memory writes, no direct workflow runs, no risk classification.
- **Depends on:** **100F** (closed / ACCEPTED).
- **Code today:** no `app/router/` package. `AuditEventType.ROUTER_DECISION` exists in `enums.py` but is **not emitted** anywhere. Subsystem **entrypoints** already exist: LangGraph `POST /v1/directives/{id}/workflow/run`; MCP `POST /v1/mcp/classify|execute`; Nike `POST/GET /v1/nike/events...`; memory read `GET /v1/memory/directive/{id}` (and project scope).
- **Document conflict:** **Resolved** under **`DOC_100G_CONFLICT_RESOLUTION`** — LLM routing moved to **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100R_MODEL_ROUTER_LOCAL_FIRST.md`**; **100G** file rewritten as subsystem router.

### Plan (Step 2 — Plan, pre-build)

1. **Modules (as issued):** `backend/app/router/router_service.py`, `router_classifier.py`, `router_validator.py`, `router_logger.py`.
2. **Input:** `directive_id`, `task_id`, `agent_role`, `intent` (string or small enum), `payload` (JSON, optional) — same identity validation pattern as **100F** MCP (directive exists; task belongs to directive; agent role normalized).
3. **Output:** JSON `{ "route": "MCP|LANGGRAPH|NIKE|MEMORY", "reason": "...", "next_action": "...", "validated": true|false }` — `next_action` = suggested HTTP path or operation id **only** (caller executes), not an inline execution.
4. **Classifier:** map `intent` → route per boundaries: execution intent → **MCP**; workflow progression → **LANGGRAPH**; event propagation → **NIKE**; read-only knowledge → **MEMORY**; **ambiguous/unknown → fail closed** (`validated: false`, no route or explicit `AMBIGUOUS`).
5. **Logging:** add `AuditEventType.ROUTER_DECISION_MADE` (or program-approved alias); payload includes `intent`, `route`, `reason`, `next_action`, `directive_id`, `task_id` (no secrets). `router_logger.py` uses `AuditRepository` + directive `workspace_id` / `project_id`.
6. **API:** `POST /api/v1/router/route` (or `/router/decide`) — body = input contract; response = output contract; **no calls** to MCP, memory, Nike, or workflow from router code path (static strings for `next_action` only).
7. **Tests:** table tests for each route + ambiguous fail-closed; invalid FK / bad input → 4xx; assert router module does not import subprocess / mcp execute client / memory writer; optional `ast` scan like **100F** for forbidden imports.
8. **Proof (for later build):** sample audits `ROUTER_DECISION_MADE` for all four routes; show no DB mutation beyond audit row (and no proof_objects unless program requests).

### Plan Decision

**PENDING** — await program **ACCEPTED** on this plan (and resolution of conflict with legacy `TRIDENT_IMPLEMENTATION_DIRECTIVE_100G_ROUTER.md` if required). **No Step 3 Build** until then.

### Unlock

After plan ACCEPT + build + proof: **100H+** per program.

---

## Directive: 100G — Step 3 Build (subsystem router)

**Status:** PASS

### Plan Decision

**ACCEPTED** — program authorized Step 3 Build; constraints restated in issued message (pure decision layer; no MCP/LangGraph/Nike execution calls).

### Build Summary

`backend/app/router/` (`router_classifier`, `router_validator`, `router_logger`, `router_service`); `POST /api/v1/router/route`; routes **MCP | LANGGRAPH | NIKE | MEMORY**; ambiguity → `validated: false`; audit **`ROUTER_DECISION_MADE`** every call; `clawbot_100g_proof.py`.

### Files Changed

`trident/backend/app/router/**`, `trident/backend/app/schemas/router.py`, `trident/backend/app/api/v1/router_route.py`, `trident/backend/app/api/routes.py`, `trident/backend/app/models/enums.py`, `trident/backend/tests/test_router_100g.py`, `trident/backend/clawbot_100g_proof.py`, `trident/backend/Dockerfile`.

### Commands Run

`python3 -m pytest` — **69 passed** (includes `tests/test_router_100g.py`).

### Proof

- **Git:** implementation **`1595f05`**, proof script fix **`efccb69`** (verify `git log -2 --oneline` on `main`).
- **Clawbot (`2026-04-30`):** `docker compose exec trident-api python clawbot_100g_proof.py` → four `route_*_status=200`, `ambiguous_status=200`, `router_decision_made_count=5`, **`100g_clawbot_proof_ok=1`**.

### Gate Decision

**PASS** — unit tests + clawbot proof green.

### Unlock

**100H** authorized only after program gate on clawbot receipt (this section satisfies engineering proof).

---

## Directive: 100G_FINAL — Program acceptance

**Status:** PASS **(ACCEPTED)**

### Gate Decision

Program **ACCEPTED** **100G_FINAL** — subsystem router implementation + clawbot proof closed; **100H** may proceed under governed execution.

---

## Directive: 100H — Agent execution layer

**Status:** **CONDITIONAL PASS** — code + unit/integration proof **PASS**; **final program acceptance blocked** until **100H_FINAL clawbot** (Postgres + deployed stack) **PASS**

### Plan (Step 1 — Read)

- **Issued:** program message — controlled agent work **only** through LangGraph → agent → MCP → receipts → governed memory + audit; **no** direct subprocess/shell, file/Git, lock bypass, or MCP bypass.
- **Depends on:** **100G** (ACCEPTED).
- **ID alignment (resolved):** Web UI directive renamed to **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100U_UI.md`**, ID **100U**. **100H** is **Agent Execution Layer (backend)** only — **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100H_AGENT_EXECUTION_LAYER.md`**. Program doc: **DOC_100H_CONFLICT_RESOLUTION**.
- **Code today:** LangGraph spine (`app/workflow/spine.py`) runs **`record_node`** + **`MemoryWriter.write_from_graph`** checkpoints; **engineer** node invokes **`app/agents/`** (`run_engineer_agent_phase` → **`MCPService.execute`** + **`MemoryWriter.write_from_graph`**). **MCPService** performs classify/execute with receipts; **MemoryWriter** enforces nonce + ledger + agent_role alignment for graph writes.
- **AgentRole enum** today: `ARCHITECT`, `ENGINEER`, `REVIEWER`, `DOCUMENTATION`, `SYSTEM`, `USER` — issued types include **DEBUGGER** and **DOCS** (map **DOCS → DOCUMENTATION** or extend enum in plan acceptance).

### Plan (Step 2 — Plan, pre-build)

1. **Layout:** `backend/app/agents/` — `agent_registry.py`, `agent_context.py`, `agent_executor.py`, `agent_service.py`, `agent_logger.py` (audit helpers).
2. **Invocation boundary:** Agents run **only** when called from **compiled LangGraph nodes** (same session/run nonce as today); `AgentExecutor.run(...)` receives `directive_id`, `task_id`, `agent_role`, node `context` dict, scoped **memory snapshot** (reuse `MemoryReader` / scoped query — read-only).
3. **Output schema:** Pydantic model matching issued JSON: `decision`, optional structured `mcp_request`, optional `memory_write`, `status` ∈ `CONTINUE | COMPLETE | BLOCKED`.
4. **MCP path:** If `mcp_request` present, translate to existing **`MCPExecuteRequest`** (or internal call to `MCPService.execute`) — **single code path** to execution; agents never call subprocess or HTTP to MCP aside from in-process service call (still “through MCP layer”).
5. **Memory path:** If `memory_write` present, call **`MemoryWriter.write_from_graph`** only (same validations as spine checkpoints); reject writes if agent_role / nonce mismatch.
6. **Audits:** Add `AuditEventType` values **`AGENT_INVOCATION`**, **`AGENT_DECISION`**, **`AGENT_MCP_REQUEST`**, **`AGENT_RESULT`**; `agent_logger.py` records chain tied to `directive_id` / workspace / project.
7. **Registry:** Map **ENGINEER**, **REVIEWER**, **DEBUGGER**, **DOCS** (→ DOCUMENTATION or new role) to handler stubs or strategy objects; start deterministic/simulated decisions like current spine until model-backed behavior is in scope.
8. **Tests:** Agent module must not contain `subprocess` / `os.system`; integration tests with DB + `TestClient` optional; unit tests prove MCP invocation goes through `MCPService`, memory through `MemoryWriter`, audits ordered.
9. **Proof (later build):** LangGraph invokes agent node → MCP receipt row + memory row + full audit chain; static ban-list import test like **100G**.

### Plan Decision

**ACCEPTED IN PRINCIPLE** — Step 1–2 technical direction stands.

### Enforcement (100H scope — program)

- No UI responsibilities  
- No direct execution (agents route MCP **only** via `MCPService`)  
- No subprocess / shell  
- No file or Git mutation  
- No MCP bypass  
- No memory bypass (`MemoryWriter.write_from_graph` only)  
- No Nike reasoning  
- No router scope expansion  

### Build status

**DOC_100H_CONFLICT_RESOLUTION:** **PASS** (accepted **`60df87f`**). **Step 3 implementation:** merged on **`main`** (see **`100H_FINAL`**). **Program closure:** **pending** **`100H_FINAL` clawbot PASS**.

### Unlock

**100I** — **BLOCKED** until program **ACCEPT** on **`100H_FINAL`** with **clawbot Postgres + runtime** proof (below). **Do not** add UI (**100U**); **do not** expand agent behavior; **do not** bypass MCP or **`MemoryWriter`**.

### Engineering proof (Step 3 — local)

- **`pytest`:** full **`trident/backend`** suite green (includes **`tests/test_agents_100h.py`**).
- **Chain:** engineer spine node → **`run_engineer_agent_phase`** → **`AGENT_*`** audits → **`MCPService.execute`** → **`MemoryWriter.write_from_graph`** → **`AGENT_RESULT`**.
- **Commit:** git **`HEAD`** on **`main`** — message prefix **`feat(100H): agent execution layer`** (see **`100H_FINAL`**).

---

## Directive: DOC_100H_CONFLICT_RESOLUTION

**Status:** **PASS** — program **ACCEPTED** at **`60df87f`**

### Summary

- Renamed UI directive: **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100H_UI.md`** → **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100U_UI.md`** (git rename; content updated for **100U**).
- Added **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100H_AGENT_EXECUTION_LAYER.md`** — **Agent Execution Layer (backend); no UI responsibilities.**
- Updated **Manifest v1.0**, **Master Execution Guide v1.0 / v1.1**, **Governed Execution Playbook v1.0 / v1.1**, **100G / 100I / 100J / 100K** manifest links, **000P** placement line, **FIX 006** example chain, and **DIRECTIVE_WORKFLOW_LOG** (W-014).
- Ordering: **100G → 100H (Agents) → 100I → 100J → 100L (Production hardening) → 100U (UI) → 100K (IDE) → 100P → …**

### Gate Decision

**ACCEPTED** — **100H** = Backend Agent Execution Layer; **100U** = Web UI / Presentation Layer; **100H Step 3 Build** authorized.

---

## Directive: 100H_FINAL — Engineering proof (Step 3)

**Status:** **CONDITIONAL PASS** — **local engineering PASS**; **CLAWBOT PROOF REQUIRED** for final acceptance

### Proof checklist (local — filled)

- **Scope:** `app/agents/` — `schemas`, `agent_context`, `agent_logger`, `agent_registry`, `agent_executor`; **`engineer`** spine node calls **`run_engineer_agent_phase`** after **`record_node`**.
- **Audits (expected for workflow directive):** `AGENT_INVOCATION` → `AGENT_DECISION` → `AGENT_MCP_REQUEST` → `MCP_EXECUTION_REQUESTED` → `MCP_EXECUTION_COMPLETED` → `MEMORY_WRITE` → `AGENT_RESULT` as an **ordered subsequence** (other audits such as `MEMORY_READ_ACCESS` may interleave; clawbot does **not** require adjacency).
- **Memory:** Stub supplies **`memory_write`** → **`MemoryWriter.write_from_graph`** only; structured row authoritative; **vector** state recorded (**`VECTOR_INDEXED`** preferred when Chroma healthy).
- **Hygiene:** `app/agents/**/*.py` contains **no** `subprocess` / `os.system` (see **`tests/test_agents_100h.py`**).
- **Tests:** `cd trident/backend && python3 -m pytest -q` — full suite green in engineering CI/local.

### RUN ORDER — 100H FINAL CLAWBOT PROOF

**Gate:** **`100H_FINAL` = CONDITIONAL PASS** · **`100I` = LOCKED** until live clawbot proof below **PASS**es.

**Complete (already):** local tests · proof harness **`clawbot_100h_proof.py`** · no-bypass guard · **`WORKFLOW_LOG`** governance · explicit PASS marker list.

**Not complete:** live clawbot runtime proof — operator/engineering runs:

```bash
ssh jmiller@clawbot.a51.corp
cd ~/code_projects/trident/trident/trident
git pull origin main
docker compose down
docker compose up -d --build
docker compose exec trident-api python -m alembic upgrade head
export TRIDENT_GIT_HEAD=$(git rev-parse HEAD)
docker compose exec -e TRIDENT_GIT_HEAD="$TRIDENT_GIT_HEAD" trident-api python clawbot_100h_proof.py
docker compose restart trident-api
```

Restart verification (use **`TRIDENT_100H_VERIFY_DIRECTIVE_ID`** printed by the first script):

```bash
docker compose exec trident-api env TRIDENT_100H_VERIFY_DIRECTIVE_ID='<directive_id_from_script>' python clawbot_100h_proof.py
docker compose ps
```

Script: **`trident/backend/clawbot_100h_proof.py`** (in **`trident-api`** image). Validates ordered audit subsequence, MCP **`EXECUTION_LOG`** proof, **`agent:engineer`** memory row, directive **`COMPLETE`** / ledger **`CLOSED`**, and **`MCP_no_bypass_guard`** (**each `MCP_EXECUTION_COMPLETED` has `AGENT_MCP_REQUEST` in the audit window since the prior completion**).

### Required PASS markers (all must be present — **do not unlock 100I** otherwise)

```text
100h_clawbot_proof_ok=1
MCP_no_bypass_guard: PASS
restart_verify_PASS=1
directive COMPLETE
ledger CLOSED
agent:engineer memory row
EXECUTION_LOG proof object
```

First run must also show **`Status: PASS`** and exit **0**; restart run must show **`Status: PASS`**, **`restart_verify_PASS=1`**, exit **0**.

**Return:** paste **full stdout/stderr** from both script invocations plus **`docker compose ps`** output to program.

### Return template (paste back to program)

```text
Directive: 100H_FINAL
Status: PASS | FAIL
Git HEAD:
Alembic current:
Workflow run output:
Agent invocation proof:
MCP receipt proof:
Memory write proof:
Audit chain proof:
Directive/ledger final state:
Restart persistence:
docker compose ps:
Known gaps:
```

### Commit

Merge on **`main`**: **`feat(100H): agent execution layer — LangGraph engineer hook, MCP, audits`** (+ **`clawbot_100h_proof.py`** when merged)

---

## Directive: DOC_MODEL_CADRE_INTEGRATION — Model cadre architecture alignment

**Status:** **PASS** (documentation-only; **no code**, **no APIs**, **no model runtime**)

### Summary

Formal integration of **model cadre** policy across **Manifest v1.0**, **Master Execution Guide v1.1**, **000G**, **100R**, **100H**, **100I**, and workflow logs.

**Architecture rule:** **SINGLE_MODEL_MODE** (one shared local model) and **CADRE_MODE** (per-role model profiles: Architect / Engineer / Reviewer / Debugger / Docs). **Local-first**; **RTX 6000–class 32GB VRAM** planning target; **external OpenAI/API fallback only**. Provisional model names are **candidates** until **100R** benchmarks validate — **not** hard-coded production choices.

### Placement

| Directive | Role |
|-----------|------|
| **100I** | E2E validation only; **must not** implement LLM routing; **must** verify design **does not block** future per-agent assignment |
| **100R** | Implements registry, cadre modes, local-first routing, fallback policy, fallback-reason logging, token/cost logging, health checks, VRAM-fit benchmarks |
| **100H** | No model routing; avoid coupling that blocks **100R** |

**Forbidden:** Model routing in Nike, MCP, or IDE.

### Gate (program)

~~**100I planning / implementation remain paused** until program **ACCEPT** on this bundle.~~ **CLOSED — ACCEPTED.**

### Architect decision

**`DOC_MODEL_CADRE_INTEGRATION = PASS`**. **`100I = UNBLOCKED`** (Read + Plan satisfied; **Step 3 — Build authorized**). Architecture consistent: cadre defined; **100I** validation-only; **100R** owns selection/routing/economics; **no** leakage into Nike / MCP / subsystem router / IDE. **No retroactive sync** to Master Guide v1.0 or Playbook (**v1.1** authoritative; hygiene deferred).

### Commit

**`508c109`** — `docs(DOC_MODEL_CADRE_INTEGRATION): model cadre policy; 100I vs 100R scope`

---

## Directive: **100I** — Step 3 Build **AUTHORIZED**

**Status:** **BUILD AUTHORIZED** (proof **not** yet returned)

### Scope (validate only)

```text
Router → LangGraph → Agent → MCP → Memory → Audit → Proof → Final State
```

### Enforcement

Do **not**: implement model routing (**100R**); call external APIs for routing; add product features; modify agent behavior; expand **100G** router scope; introduce UI logic (**100U**).

### Proof

**Mandatory:** **clawbot** (Postgres + compose) — full stdout/package; **not** local-only. Return template lines:

```text
Directive: 100I
Status: PASS | FAIL
Routing proof:
Workflow execution proof:
Agent execution proof:
MCP proof:
Memory proof:
Audit chain proof:
Proof objects:
Final state:
Restart persistence:
Bypass violations:
```

### RUN ORDER — 100I CLAWBOT PROOF

Script: **`trident/backend/clawbot_100i_proof.py`** (API image). Validates **Router** (`POST …/router/route` → **ROUTER_DECISION_MADE**) → **`workflow/run`** → agent/MCP/memory/audit/proof chain + restart verify. On success the script prints **`=== Program acceptance return (copy from here) ===`** with the bullet checklist (**Routing / Workflow / Agent / MCP / Memory / Audit / Proof objects / Final state / Restart / Bypass / Markers / Known gaps**) matching program acceptance; paste **both** primary + verify invocations for full marker evidence.

```bash
ssh jmiller@clawbot.a51.corp
cd ~/code_projects/trident/trident/trident
git pull origin main
docker compose down
docker compose up -d --build
docker compose exec trident-api python -m alembic upgrade head
export TRIDENT_GIT_HEAD=$(git rev-parse HEAD)
docker compose exec -e TRIDENT_GIT_HEAD="$TRIDENT_GIT_HEAD" trident-api python clawbot_100i_proof.py
docker compose restart trident-api
docker compose exec trident-api env TRIDENT_100I_VERIFY_DIRECTIVE_ID='<directive_id_from_script>' python clawbot_100i_proof.py
docker compose ps
```

**Required PASS markers (full run):** `Status: PASS`, exit **0**, **`100i_clawbot_proof_ok=1`**, **`ROUTER_DECISION_MADE_present=True`**, **`MCP_no_bypass_guard: PASS`**, **`Directive_final_status: COMPLETE`**, **`Ledger_final_state: CLOSED`**, **`EXECUTION_LOG`** UUID printed.

**Verify run:** **`restart_verify_PASS=1`**, **`100i_clawbot_proof_verify_ok=1`**, exit **0**.

API prefix: when deployed behind **`/trident`**, ensure **`TRIDENT_BASE_PATH=/trident`** on **`trident-api`** so in-container HTTP calls hit **`/trident/api/v1/...`**.

---

## Directive: **100I_FINAL** — Program ACCEPT

**Status:** **PASS** — **ACCEPTED**

### Accepted proof (clawbot)

- **Git HEAD:** **`c6378e0`**
- **Verify directive:** **`7ef53f28-c5fe-4804-bb6c-61c517eebdb1`**
- **Router / workflow / agent / MCP / memory / audit chain / restart persistence / bypass:** **PASS**
- **Final state:** directive **`COMPLETE`**, ledger **`CLOSED`**

### Next

**100J** — Deployment + Production Validation — authoritative file: **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100J_DEPLOYMENT_PRODUCTION_VALIDATION.md`** (canonical name; do not use alternate filenames).

**100J_PLAN:** **ACCEPTED** — Step 3 Build/Execute authorized (validation only; **no** UI/perf expansion; **no** agents/router/MCP/memory/Nike/model routing changes).

---

## Directive: **100J_FINAL** — Deployment + Production Validation

**Status:** **PASS** — **ACCEPTED** (clawbot Step 3 executed)

### Proof summary (2026-04-30 clawbot)

- **Git HEAD (host pull):** **`3c31e6c`**
- **Compose:** `docker compose down` → `build --no-cache` → `up -d`; final **`docker compose ps`** — core services **healthy** (api, db, chroma, web, exec; worker up).
- **Alembic:** **`100e001 (head)`** after deploy.
- **Persistence:** **`audit_events` = 215**, **`memory_entries` = 25** before full-stack down; **unchanged** after `up` (Postgres volume intact).
- **100I re-validation (post-deploy):** **`Status: PASS`**, **`100i_clawbot_proof_ok=1`**; after **`docker compose restart trident-api`**: **`restart_verify_PASS=1`**, **`100i_clawbot_proof_verify_ok=1`**, verify directive **`31e10b91-d605-4d8f-a19c-97c0db3a2366`**, **`EXECUTION_LOG`:** **`d84af3d4-8f01-49b8-a98a-9e9b2c7bab8e`**.
- **Security / enforcement:** Matches **100I** acceptance (MCP guard, audit chain, routing/workflow proofs); log tail reviewed — **Chroma telemetry** noise only (no secrets flagged).

### Known issue (probe documentation)

Host **`curl http://127.0.0.1:8000/api/{health,ready,version}`** returned **FAIL** (404 in logs) because **`trident-api`** is mounted with **`TRIDENT_BASE_PATH=/trident`** — correct paths are **`/trident/api/health`** (etc.). Docker **healthy** status and in-process checks use the prefixed routes.

### Out of scope (per issued constraints)

**Backup/restore**, **performance**, **UI validation** — not executed this pass (**N/A**).

### Next

**100L** — Production hardening — per manifest after **100J**; then **100U**.

---

## Directive: **100L** — Production Readiness & Operational Hardening

**Status:** **PASS** — Step 3 Build complete (authoritative proof: commit below)

### Delivered

- **`trident/docker-compose.yml`:** `restart: unless-stopped`; `cpus` / `mem_limit` per service; **trident-worker** / **trident-exec** depend on **trident-api** `service_healthy`.
- **Logging:** `app/logging_utils.py` — caps **chromadb** / **httpx** / **httpcore** noise when root level is INFO; wired in **API** + **Nike worker**.
- **`trident/docs/OPERATIONS_RUNBOOK.md`:** env matrix, startup order, restart/recovery, failure matrix, audit SQL sample, **pg_dump** / **pg_restore** outline, notes on **`TRIDENT_BASE_PATH`** health URLs.
- **Tests:** `pytest` **77 passed** (local).

---

## Directive: **100L_FINAL** — Program ACCEPT

**Status:** **CLOSED** — **ACCEPTED**

- **Accepted commits:** **`26ef506`**, **`88ecbdb`**
- **Verification:** Compose hardening, logging controls, runbook, bounded failure documentation, constraints respected; clawbot re-run **optional** (non-blocking per program).

---

## Directive: **100U** — UI Layer (Web Interface)

**Authoritative file:** **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100U_UI.md`** · **Depends on:** **100L** · **Unlocks:** **100K** · **LLD gate:** **000H**

### Step 3 Build — **PASS** → **PASS_CONFIRMED** (clawbot)

- **Bundle commit:** **`806e2c3`** · **getApiBase fix:** **`34ba2a1`** · **100U_FINAL proof bundle:** **`e224996`**
- **Stack:** React 18 + Vite + TypeScript; **`npm run build`** + **`vitest`** (2 tests) **PASS**.
- **Delivery:** `trident/frontend` — layout (nav / workspace / control rail); live **`fetch`** to **`/v1/*`** via **`getApiBase()`** (supports **`TRIDENT_PUBLIC_BASE_URL`** or same-origin proxy).
- **Nginx (100U):** `nginx.conf.template` — proxies **`${TRIDENT_BASE_PATH}/api/`** → **`trident-api`**; entrypoint sets **`TRIDENT_NGINX_LOCATION_API`**; **`docker-compose`** default **`TRIDENT_PUBLIC_BASE_URL`** empty for **trident-web** (same-origin).
- **Git panel:** limitation banner + GIT-prefixed proof types from existing memory read — **no** new Git APIs.
- **LangGraph / state:** directive detail + **`/v1/memory/directive/{id}`** (`task_ledger`, `handoffs`, entries, proofs) — **no** backend changes.
- **Backend tests:** **`pytest` 77 passed** (unchanged).
- **Docs:** **`OPERATIONS_RUNBOOK.md`** — web→API proxy note; **`docs/proof_100u_clawbot/README.md`** — clawbot capture notes.

### Clawbot mandatory verification (host **clawbot.a51.corp**)

- **`docker compose ps`:** all stack services **Up (healthy)** including **`trident-web`** on **`0.0.0.0:3000->80/tcp`**.
- **HTTP:** **`GET http://127.0.0.1:3000/`** → **200**; **`GET http://127.0.0.1:3000/trident/api/health`** → **`{"status":"ok","service":"trident-api"}`**. **`GET /api/health`** on the web port returns the SPA shell (**200 HTML**) when only **`${TRIDENT_BASE_PATH}/api/`** is proxied — use **`/trident/api/health`** for JSON under **`TRIDENT_BASE_PATH=/trident`**.
- **Run note:** **`TRIDENT_PUBLIC_BASE_URL=`** on **`trident-web`** during confirmation so the browser uses same-origin **`/trident/api`** via nginx (avoids CORS if a stale cross-origin URL was set).
- **UI screenshots:** **`trident/docs/proof_100u_clawbot/100u-directives-and-panels.png`**, **`100u-mcp-router-rail.png`**.

---

## Directive: **100U_FINAL** — Program CONFIRMED

**Status:** **CLOSED** — **PASS_CONFIRMED** (clawbot build/up/curl + UI captures).

**Architect:** **FULLY ACCEPTED** — commits **`34ba2a1`**, **`e224996`**, **`431e9ce`**. **CORE SYSTEM + UI = VERIFIED.**

**Next:** **100K** — IDE bootstrap — **ISSUED** (Phase 2).

---

## Directive: **100K** — IDE Client Bootstrap (VS Code / Code - OSS Extension)

**Authoritative file:** **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100K_IDE_BOOTSTRAP.md`** · **Depends on:** **000O**, **100U** (both **ACCEPTED**) · **Unlocks:** **100P** · **Architecture:** **`TRIDENT_DIRECTIVE_000O_CODE_OSS_IDE_CLIENT_ARCHITECTURE.md`**

### Step 1 — Read (engineering) — **COMPLETE**

**Directive intent:** Ship a **VS Code–compatible extension** that is a **thin client** of **trident-api**: configurable base URL, health/reconnect, sidebar summary, **read-only** directive list/detail, **backend-driven** chat (no local LLM / no direct external APIs), agent/router/git-lock **visibility** (read-only; **no file mutation**, **no bypass**).

**Repo:** **`trident-ide-extension/`** — VS Code extension (sidebar, chat webview, agent JSON command, health).

**Backend surface (100K Step 3):**

| Capability | API |
|------------|-----|
| Health | **`GET .../api/health`** |
| Directives list / detail | **`GET /v1/directives/`**, **`GET /v1/directives/{id}`** |
| Memory / ledger view | **`GET /v1/memory/directive/{directive_id}`** |
| IDE chat (stub) | **`POST /v1/ide/chat`** — deterministic reply; **`IDE_CHAT_REQUEST`** / **`IDE_CHAT_RESPONSE`** audits; **`ProofObjectType.CHAT_LOG`** |
| Router / locks | Unchanged — extension does **not** call **`POST /v1/router/route`** or **`POST /v1/locks/*`** in this milestone |

**Config:** Directive example **`TRIDENT_API_URL=http://localhost:8000`** — engineering will normalize to **`{TRIDENT_API_URL}{base}/api/v1/...`** matching **`main.build_app`** (**`api_router_prefix`** defaults to **`/api`**; **`TRIDENT_BASE_PATH`** prefixes the app).

**Tests:** **100K** asks for extension-load + integration-style checks — plan uses **`@vscode/test-electron`** or **`vscode-test`** style harness **where feasible**, plus documented manual proof (screenshots / sample responses) per §8.

---

### Step 2 — Plan (engineering)

**Directive: `100K_PLAN` · Status: `ACCEPTED`** (architect — minimal **`POST /api/v1/ide/chat`**, deterministic stub only, auditable, no Nike/router/agent/MCP expansion beyond route above).

**Deliverable layout:** New top-level **`trident-ide-extension/`** (or **`ide-extension/`** under repo root — pick one in Step 3; **100K** diagram uses **`trident-ide-extension/`**) with **`package.json`**, **`src/extension.ts`**, **`src/api/tridentClient.ts`**, **`src/utils/config.ts`** (**`trident.apiBaseUrl`**, **`trident.basePath`** optional), panels + sidebar as specified.

**Implementation slices (ordered):**

1. **Scaffold + config + client** — VS Code extension activation; **`TridentClient`** with **`fetch`**, timeouts, **`GET /health`**, base URL normalization (**`/api/v1`**).
2. **Sidebar (`tridentSidebar.ts`)** — connection indicator; **active directive** (user picks from list or last-used stored in **`globalState`**); **placeholder project** (display-only until **100P** project registry UX); **agent snapshot** from **`GET /v1/directives/{id}`** + **`GET /v1/memory/directive/{id}`** (derive “current node” / role strings from ledger + memory, best-effort).
3. **Directive panel** — **`GET /v1/directives/`** table Webview or Tree; detail pane read-only.
4. **Agent panel** — same sources as sidebar expanded.
5. **Status panel** — last **`POST /v1/router/route`** result (user-triggered “Ping router” or auto with canned minimal body **only if** architect accepts harmless classifier demo payload); memory-sourced GIT/limitation notes like **100U**.
6. **Chat panel** — **requires minimal backend slice** in Step 3 Build (recommended): add **`IDE_USER_PROMPT`** (name TBD) **Nike event type** + **worker handler** that completes with a **deterministic, audited stub reply** (no LLM), **or** a tiny **`POST /v1/ide/chat`** that writes audit + returns JSON **`{ "reply": "..." }`** — **either way**, extension only calls **trident-api**, displays **`reply`**. **Alternative (BLOCKED path):** defer chat panel until a separate directive adds governed chat — would fail §7 chat tests; **not** recommended.

**Explicit Step 3 non-goals (per §6):** No **`POST /v1/locks/*`**, no file edits, no local OpenAI/Anthropic keys, no mocked JSON fixtures as primary source.

**Proof package (Step 3):** Extension **`README`** + Run Extension host; **`curl`** **`POST /api/v1/ide/chat`**; **`pytest`** includes **`test_ide_chat_100k`**.

---

### Step 3 — Build (engineering) — **PASS**

- **Backend:** **`POST /api/v1/ide/chat`** (`app/api/v1/ide.py`, `app/ide/chat_service.py`). **`AuditEventType`:** **`IDE_CHAT_REQUEST`**, **`IDE_CHAT_RESPONSE`**. **`ProofObjectType.CHAT_LOG`**. No Nike/router/MCP/agent behavior changes beyond this route.
- **Tests:** **`tests/test_ide_chat_100k.py`**; full **`pytest`** **79 passed**.
- **Extension:** **`trident-ide-extension/`** — `TridentClient`, activity-bar sidebar, chat webview → **`/api/v1/ide/chat`**, commands for agent/memory JSON and health. **`README.md`** + **`.vscode`** launch/tasks.

**Directive: `100K` · Status: `PASS`** — proof **`dc5e2dc`** (+ doc **`08195af`**).

---

## Directive: **100K_FINAL** — Program CLOSED

**Status:** **CLOSED** — **ACCEPTED**

- **Verification:** IDE chat endpoint (deterministic stub); **`IDE_CHAT_REQUEST`** / **`IDE_CHAT_RESPONSE`**; **`CHAT_LOG`** proof; no Nike/router/agent/MCP/memory drift; extension functional; **`pytest` 79**.
- **Accepted commits:** **`dc5e2dc`**, **`08195af`**.
- **System state:** **FULL STACK (CORE + UI + IDE STUB) = VERIFIED.**

**Next:** **100P** — IDE file lock integration — **ISSUED**.

---

## Directive: **100P** — IDE File Lock + Governed Edit Flow

**Authoritative file:** **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100P_IDE_FILE_LOCK.md`** · **Depends on:** **100K** (**ACCEPTED**) · **Unlocks:** **100M** · **Related:** **`TRIDENT_FIX_DIRECTIVE_001_IDE_WRITE_GATE_ENFORCEMENT.md`** (must complete before **100M**/**100N** per FIX manifest)

### Step 1 — Read (engineering) — **COMPLETE**

**Directive intent:** Enforce **backend-authoritative file locks** in the Trident IDE: no governed edit without **`POST /api/v1/locks/acquire`** success; validate ownership during editing; release via **`POST /api/v1/locks/release`**; visible lock state / rejection UX; Git awareness (diff/dirty/branch) per §9.

**Backend (100E + 100P Step 3):**

| Endpoint | Role |
|----------|------|
| **`GET /api/v1/locks/active`** | Read-only active lock for **`project_id`** + relative **`file_path`** (respects **`expires_at`**) |
| **`POST /api/v1/locks/acquire`** | Unchanged request shape; optional **`TRIDENT_LOCK_TTL_SEC`** sets **`expires_at`** |
| **`POST /api/v1/locks/release`** | Unchanged |
| **`POST /api/v1/locks/simulated-mutation`** | Unchanged semantics; stale TTL rows expired before lock lookup |

**Identity / Git:** Extension settings **`trident.projectId`**, **`trident.userId`**, **`trident.agentRole`**; **no** backend Git status API in **100P** (architect constraint). **FIX 001:** Hybrid interception — **`README`** documents residual bypass (shell/external editors outside VS Code).

---

### Step 2 — Plan (engineering)

**Directive: `100P_PLAN` · Status: `ACCEPTED`** — log **`7ff7a7d`** / **`b35df98`**; architect-approved **`GET /active`**, optional TTL, no Git API / no VFS / no router-agent-memory drift.

**FIX 001 — chosen approach (baseline):** **Hybrid (1+2 lite)** — primary: **VS Code extension document change interception** via **`onWillSaveTextDocument`** (block save) + **`onDidChangeTextDocument`** / **`WorkspaceEdit`** rollback for **governed** files when lock invalid (best-effort; cannot defeat `echo >> file` outside VS Code). Document **cannot-prevent** paths (external processes, other workspaces). Defer **virtual FileSystemProvider** / **Code-OSS fork** to future unless architect escalates.

**Backend slices (minimal, no router/agent/MCP/Nike drift):**

1. **`GET /api/v1/locks/active`** — query `project_id` + relative `file_path`; returns active lock metadata (**`lock_id`**, **`directive_id`**, **`locked_by_user_id`**, **`locked_by_agent_role`**, **`expires_at`**) or **404**; treats **`expires_at < now`** as inactive. Read-only; no new write behavior.
2. **Optional TTL:** Set **`expires_at`** on acquire from settings (e.g. **`TRIDENT_LOCK_TTL_SEC`**) and enforce in **`GET` + acquire conflict paths** — only if architect confirms desired semantics.

**Extension (`trident-ide-extension/`):**

| Planned path | Responsibility |
|--------------|------------------|
| **`src/locking/lockClient.ts`** | Wrap acquire / release / active-get |
| **`src/locking/lockInterceptor.ts`** | Map workspace **`Uri`** → repo-relative path vs **`Project.allowed_root_path`** (client-side prefix check mirroring backend rules where possible) |
| **`src/editors/editGuard.ts`** | Subscribe save + change events; consult cache + **`GET .../locks/active`** throttle; block / rollback; status bar + decorations |
| **Settings** | **`trident.projectId`**, **`trident.userId`**, **`trident.agentRole`** (default **`USER`**) |
| **Commands** | **Acquire lock for active editor**, **Release lock**, **Refresh lock badge** |

**Tests:**

- **Backend:** **`pytest`** for **`GET /locks/active`** + TTL/expiry if implemented.
- **IDE / integration:** Harness or manual proof per §11–12 (blocked vs allowed edit, conflict); screenshots + audit samples for FIX 001 §7.

**Explicit non-goals for Step 3 (unless architect expands):** No change to **simulated-mutation** semantics; no **memory/router** coupling; no replacing **PostgreSQL** lock rows with local-only state.

---

### Step 3 — Build (engineering) — **PASS**

- **Backend:** **`GET /api/v1/locks/active`**; **`find_active_lock`** filters expired locks; **`TRIDENT_LOCK_TTL_SEC`** (`Settings.lock_ttl_sec`) optional on acquire; **`_expire_stale_locks_for_path`** releases TTL-expired rows (**`LOCK_RELEASED`** payload **`ttl_expired`**) before acquire / simulated mutation; **`get_settings_dep(Request)`** resolves **`app.state.settings_ref`** for **`build_app(cfg)`** parity.
- **Tests:** **`tests/test_locks_active_100p.py`**; **`pytest` 83 passed**.
- **Extension:** **`src/locking/lockClient.ts`**, **`lockInterceptor.ts`**, **`src/editors/editGuard.ts`** — **`onWillSave`** blocks save without valid lock; debounced **`onDidChange`** rollback; **`trident.acquireLock` / `trident.releaseLock`**; governance **`OutputChannel`**.

**Directive: `100P` · Status: `PASS`** — proof **`565b6ae`** (+ doc **`c162fca`**).

---

## Directive: **100P_FINAL** — Program CLOSED

**Status:** **CLOSED** — **ACCEPTED**

- **Verification:** **`GET /api/v1/locks/active`**; optional TTL; IDE save block + rollback; identity settings; server lock authority; no Git API / VFS / agent-router-memory drift; **`pytest` 83**.
- **Accepted commits:** **`565b6ae`**, **`c162fca`**.
- **Follow-up (non-blocking):** **FIX 001** proof artifacts (screenshots / audit samples) if tracked separately.

**Next:** **100M** — IDE patch + apply workflow — **ISSUED**.

---

## Directive: **100M** — IDE Patch + Apply Workflow

**Authoritative file:** **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100M_PATCH_APPLY_WORKFLOW.md`** · **Depends on:** **100P** (**ACCEPTED**) · **Unlocks:** **100N** · **Architecture:** **`TRIDENT_DIRECTIVE_000O_CODE_OSS_IDE_CLIENT_ARCHITECTURE.md`**

### Step 1 — Read (engineering) — **COMPLETE**

**Directive intent:** **Cursor-style** pipeline: change requests produce a **reviewable unified diff** (§6); **preview UI** (§8); **approve / reject** (§11); on approve → **validate lock + Git context + directive** (§9) → **apply** → **proof + audit** (§10). **No silent direct edits** through this workflow (§3, §13).

**Repo / backend today:**

| Piece | Today |
|-------|--------|
| **Locks + Git validation + diff proof** | **`POST /api/v1/locks/simulated-mutation`** (100E): active lock ownership, **`git_service`** validation, **`ProofObjectType.GIT_DIFF`**, audits (**GIT_STATUS_CHECKED**, **DIFF_GENERATED**, etc.) — **apply-like** server path exists but **no IDE preview/reject** split |
| **Patch propose / preview API** | **None** — §4 “backend returns proposed patch” implies **new read-only or idempotent propose endpoint** and/or **100N** agent integration later; **100M** Step 3 likely starts with **deterministic / stub** propose or **client-generated** patch validated server-side |
| **IDE structure** | Directive §5: **`src/patch/{patchClient,patchViewer,patchApplier,patchValidator}.ts`** — greenfield under **`trident-ide-extension/`** |
| **Direct editing** | **100P** **`editGuard`** still allows normal typing when lock valid — **100M** §13 conflicts at product level (“all edits go through patch system”) — Step 3 must **reconcile**: e.g. governance mode switches to **patch-only apply** for governed files, or scope **100M** to **agent-proposed** edits only (architect clarification) |

**Program gate (Master Execution Guide v1.1 §5, FIX 003 §8):** **FIX 003 — Lock heartbeat + expiry** (**`TRIDENT_FIX_DIRECTIVE_003_LOCK_HEARTBEAT_EXPIRY.md`**) is **mandated before 100M / 100N**. Current stack has **TTL / `expires_at`** (**100P**) but **not** heartbeat interval, **`STALE_PENDING_RECOVERY`**, force-release policy, or IDE refresh loop per FIX 003.

---

### Step 2 — Plan (engineering)

**Directive: `100M_PLAN` · Status: `BLOCKED (CONFIRMED)`** — log **`695babc`** / **`19ac3be`**

**Reason:** **`TRIDENT_MASTER_EXECUTION_GUIDE_v1_1.md`** §5 and **`TRIDENT_FIX_DIRECTIVE_003`** §8 require **FIX 003** completion **before** **100M** Step 3 Build. Engineering cannot authorize **100M** implementation until **FIX 003** is **scoped + ACCEPTED** (or the **program issues a written waiver** of that gate).

---

### Architect confirmation — **100M** **BLOCKED_CONFIRMED**

**Directive: `100M` · Status: `BLOCKED_CONFIRMED`**

**Authority cited:** Master Execution Guide **v1.1** §5; **`TRIDENT_FIX_DIRECTIVE_003_LOCK_HEARTBEAT_EXPIRY.md`** §8.

**Finding:** **100P** TTL / **`expires_at`** does **not** satisfy **FIX 003** (heartbeat, stale/recovery model, visibility guarantees).

**Required program decision** — pick one before any **100M** Step 3 work:

| Option | Meaning |
|--------|---------|
| **A (default)** | Implement **FIX 003** first → then resume **100M**. |
| **B (override — not preferred)** | Proceed **100M** without **FIX 003** only after **explicit** acceptance of risk: stale locks, ownership edge cases, missing heartbeat/recovery guarantees. |

**Next state:** **`WAITING_FOR_PROGRAM_DECISION (FIX_003 vs WAIVER)`** — **superseded:** architect issued **FIX_003** (**Option A / best practice**); **100M** stays **BLOCKED** until **FIX_003** is **PASS** / **ACCEPTED**.

**Receipt:** **`a0b89de`** (**W-030**).

**When unblocked — intended Step 3 slices (preview):**

1. **FIX 003** (or waiver) — heartbeat / stale semantics per fix doc; align with existing **`LockStatus`** / TTL or extend schema with migrations + audits.
2. **Backend:** Thin **`POST /api/v1/ide/patch/validate`** (unified diff + directive/project/file context, lock check, git sanity) returning structured errors; **`POST /api/v1/ide/patch/apply`** wrapping or delegating to **`simulated-mutation`**-grade validation + **`GIT_DIFF`** proof — **no** hidden multi-file apply in MVP.
3. **Extension:** **`patchViewer`** (webview diff), **`patchApplier`** calling validate → apply; **`patchValidator`** client-side lint (paths, `..` rejection); integrate **100P** lock acquisition prompts.
4. **Tests:** **`pytest`** for new routes; VS Code manual / harness proof for preview/reject/apply; §14 cases.

**Non-blocking:** **FIX 001** supplemental artifacts (architect **100P** note).

**To return `100M_PLAN` → `READY`:** **FIX_003** complete (**below**) → then **100M** Step 2 replan/ACK per manifest.

---

## Fix directive: **FIX_003** — Lock Heartbeat + Expiration Consistency

**Authoritative file:** **`TRIDENT_FIX_DIRECTIVES_001_005/TRIDENT_FIX_DIRECTIVE_003_LOCK_HEARTBEAT_EXPIRY.md`** · **Depends on:** **000E**, **100E**, **100P** · **Unlocks (gate):** **100M**, **100N**

### Step 1 — Read (engineering) — **COMPLETE**

**Directive requires:** Per-lock **heartbeat timestamp**; clients refresh on an interval; backend marks locks **stale** after **missed-heartbeat threshold**; stale enters **`STALE_PENDING_RECOVERY`**; **policy-based recovery** + owner/admin paths; **audits** for heartbeat, expiry, takeover/recovery/force-release; states **`ACTIVE` / `STALE_PENDING_RECOVERY` / `EXPIRED` / `RELEASED` / `FORCE_RELEASED` / `CONFLICTED`**.

**Repo today (100E / 100P):**

| Topic | Today |
|-------|--------|
| **`LockStatus`** | **`ACTIVE`**, **`RELEASED`** only (`app/locks/constants.py`) |
| **`file_locks`** | **`expires_at`** (optional TTL on acquire); **no** `last_heartbeat_at`; **`lock_status`** string |
| **Partial unique index** | One row per **`(project_id, file_path)`** among **`ACTIVE`** + **`released_at IS NULL`** |
| **API** | **`POST .../locks/acquire`**, **`release`**, **`simulated-mutation`**; **`GET .../locks/active`** (100P) |

**Implication:** Heartbeat + stale/recovery **extends** the model (new column(s), new statuses, new routes). **`STALE_PENDING_RECOVERY`** rows **must not** satisfy **`find_active_lock` / editing**; they **should not** participate in the **ACTIVE** partial unique index so a **new `ACTIVE`** lock can appear after takeover policy (see Step 2).

---

### Step 2 — Plan (engineering)

**Directive: `FIX_003_PLAN` · Status: `READY`** — log **`d9be1bf`** (**W-031**)

**Architect constraints honored in plan:** **`POST .../locks/acquire`** and **`POST .../locks/release`** **request/response schemas unchanged** (behavior may set **`last_heartbeat_at`** internally on acquire). **No** Git / MCP / agent / router / memory subsurface changes. **Server-authoritative** stale transitions.

**Phase — data model**

1. **Alembic:** Add **`last_heartbeat_at`** (timestamptz, nullable → backfill **`now()`** for existing **`ACTIVE`** rows); extend **`LockStatus`** with **`STALE_PENDING_RECOVERY`**, **`EXPIRED`**, **`FORCE_RELEASED`**, **`CONFLICTED`** (reserve semantics in code comments).
2. **Partial unique index:** Keep **only** **`lock_status = 'ACTIVE'`** + **`released_at IS NULL`** so **`STALE_*`** rows do not block re-acquire after takeover.

**Phase — heartbeat & staleness**

3. **Settings:** e.g. **`TRIDENT_LOCK_HEARTBEAT_INTERVAL_SEC`** (client hint / logging), **`TRIDENT_LOCK_HEARTBEAT_MISS_SEC`** (server: no heartbeat longer than this ⇒ stale). Document interaction with existing **`TRIDENT_LOCK_TTL_SEC`** (**TTL** = absolute ceiling; **heartbeat** = liveness — both enforced in **`find_active_lock`**).
4. **`LockService.acquire`:** Initialize **`last_heartbeat_at = now()`** (additive internal field).
5. **New route **`POST /api/v1/locks/heartbeat`**** — body mirrors **release** identity dimensions (**`lock_id`**, **`project_id`**, **`directive_id`**, **`agent_role`**, **`user_id`**, **`file_path`**) per strict ownership; updates **`last_heartbeat_at`** only when **`ACTIVE`**; **`409`**/`404`** when stale/wrong.
6. **Stale transition:** Shared **`_ensure_lock_liveness(session, lock_row)`** (or equivalent) invoked from **`find_active_lock`**, **`GET /locks/active`**, **`heartbeat`**, **`acquire`** prelude: if **`ACTIVE`** and missed heartbeat beyond threshold ⇒ set **`STALE_PENDING_RECOVERY`**, set audit **`LOCK_STALE`** (name TBD), optional **`released_at`** policy — **must** align with “safe takeover”: typically **do not** leave **`ACTIVE`** row occupying unique slot after stale (either status flip or release).

**Phase — recovery / takeover / force-release**

7. **Owner recovery:** **`POST /api/v1/locks/release`** — **same JSON** — extend **server behavior** to allow **idempotent / explicit release** from **`STALE_PENDING_RECOVERY`** when ownership matches (**contract-preserving**).
8. **Takeover (another principal):** After stale, **`acquire`** may succeed for same path — **`_expire_stale_locks_for_path`**-style promotion: transition prior row to **`EXPIRED`** or **`RELEASED`** with audit **`LOCK_TAKEOVER`** / **`LOCK_RECOVERED`** per policy (race-safe with transaction + row lock).
9. **Force-release:** **`POST /api/v1/locks/force-release`** — minimal **admin gate** (e.g. env allowlist **`TRIDENT_LOCK_FORCE_RELEASE_USER_IDS`** / role placeholder), **`FORCE_RELEASED`** status + audit; **no** MCP/agent/router.

**Phase — audits & visibility**

10. **`AuditEventType`:** add **`LOCK_HEARTBEAT`**, **`LOCK_STALE`**, **`LOCK_RECOVERED`** / **`LOCK_TAKEOVER`**, **`LOCK_FORCE_RELEASED`** (subset as needed for MVP vs §6 tests).
11. **IDE (extension):** **`setInterval`** heartbeat while **`heldLocks`** map populated; surface stale errors from **`GET /locks/active`** / save guard (**100P** hook).
12. **Web UI:** Minimal surfacing of stale/active (**GET active** or directives shell) — proof screenshot per §7.

**Phase — tests (FIX 003 §6)**

13. **`pytest`:** heartbeat refresh; missed heartbeat → stale; stale blocks **`find_active_lock`**; owner release from stale; force-release happy path; concurrent acquire race (sqlite + postgres if applicable).

**`FIX_003_PLAN` → `BLOCKED` triggers:** Architect forbids **any** new lock routes (would force impossible heartbeat without changing contracts — unlikely).

---

END
