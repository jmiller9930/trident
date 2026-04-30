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
- Ordering: **100G → 100H (Agents) → 100I → 100J → 100U (UI) → 100K (IDE) → …**

### Gate Decision

**ACCEPTED** — **100H** = Backend Agent Execution Layer; **100U** = Web UI / Presentation Layer; **100H Step 3 Build** authorized.

---

## Directive: 100H_FINAL — Engineering proof (Step 3)

**Status:** **CONDITIONAL PASS** — **local engineering PASS**; **CLAWBOT PROOF REQUIRED** for final acceptance

### Proof checklist (local — filled)

- **Scope:** `app/agents/` — `schemas`, `agent_context`, `agent_logger`, `agent_registry`, `agent_executor`; **`engineer`** spine node calls **`run_engineer_agent_phase`** after **`record_node`**.
- **Audits (expected for workflow directive):** `AGENT_INVOCATION` → `AGENT_DECISION` → `AGENT_MCP_REQUEST` → `MCP_EXECUTION_REQUESTED` → `MCP_EXECUTION_COMPLETED` → `MEMORY_WRITE` → `AGENT_RESULT` (ordered subsequence).
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

END
