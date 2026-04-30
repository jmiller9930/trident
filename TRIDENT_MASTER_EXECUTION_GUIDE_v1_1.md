# Project Trident — Master Execution Guide v1.1

**Document Type:** Orchestration / Single Entry Point  
**Project:** Trident  
**Status:** Active  
**Supersedes:** v1.0 (same content baseline; filename aligns execution-unlock naming)  
**Created:** 2026-04-29  
**Purpose:** One authoritative path for implementation order, dependencies, fix injection, and phase gates. Does not replace LLD or implementation directives; points to them.

```yaml
manifest_id: TRIDENT-MANIFEST-v1.0
project: Project Trident
parent_document: TRIDENT_DOCUMENT_MANIFEST_v1_0.md
document_id: TRIDENT-MASTER-EXECUTION-GUIDE-v1.1
document_type: Directive
sequence: MASTER-v1.1
status: Active
dependencies:
  - TRIDENT-DOCUMENT-MANIFEST-v1.0
  - TRIDENT-FIX-006-MASTER-EXECUTION-GUIDE
produces:
  - Clear build path for engineering
langgraph_required: true
```

---

## Policy (effective immediately)

### Source of truth for scope and proof

```text
Implementation Directive (e.g., 100A) → Master Execution Guide → Governed Execution Playbook
```

- **Scope, constraints, tests, and proof objects** are defined by the **target implementation or fix directive** first.
- This guide defines **build order**, **dependency injection**, and **when** fixes bind; it does not override directive scope.
- The playbook defines **process** (Read → Plan → Build → Prove → Review); it does not define product scope.

### Onboarding read scope (before coding)

**Required:**

- **Master Execution Guide** — relevant sections for the next step (order, §3 dependencies, §5 fix injection if applicable).
- **Governed Execution Playbook** — execution loop and templates.
- **Target implementation or fix directive** file (e.g. `TRIDENT_IMPLEMENTATION_DIRECTIVE_100A_…`).
- **LLDs and parents the directive explicitly lists** (e.g. “Parent Architecture References,” foundation/manifest pointers in the directive body — **only those references**, not the full LLD library).

**Not required:**

- Pre-reading the full **000A–000P** corpus.

**Rule:** Read only what the **target directive explicitly references**. No broad pre-reading required.

---

## 1. System Overview

Trident is a **memory-first, local-first control plane** for multi-agent software delivery. A **FastAPI (or equivalent) backend**, **worker**, **execution/MCP service**, **data and vector stores**, and **web UI** implement a single spine: **LangGraph** owns workflow and state transitions; **MCP** is the only governed execution and tool surface; **Git + file locks** gate every mutation; **shared memory + task ledger** hold durable truth; a **router** applies local-first model policy with explicit escalation; **proof and audit** close work.

### Backend as work-processing authority (IDE / Web → spine)

The **backend** is the **work-processing authority**. The **IDE** is a Cursor-style editor/frontend; the **web UI** is a control-plane frontend. **Agent workflows and agent-typed work** must run through **backend-governed** services. **Agent logic must not** be implemented as **independent IDE-side execution** (no parallel “brain” in the extension that bypasses API, Nike, LangGraph, ledger, or MCP/Git rules).

**Canonical processing chain (product runtime):**

```text
IDE / Web → Trident API → Nike → LangGraph → Agents / Memory / Router / MCP / Proof (+ Git/Lock governance)
```

**Future backend-managed agent roles** (hooks; not required to be fully implemented before Nike — Nike/event routing must admit them **without redesign**): **Engineer agent**, **Reviewer agent**, **Documentation agent**, **Debugger agent**, **Test agent**, **Security review agent**, **Performance review agent**, **Deployment/release agent**. These map to graph nodes and/or event-driven handlers **server-side** only; Nike routes events toward LangGraph and subsystems per **000P** — never as IDE-local orchestration.

**Relationships (read left as “depends on / flows from”):**

```text
Schemas + ledger (000A/000B) → LangGraph spine → memory → agents/Git/MCP/router/UI (design in 000C–000H)
Implementation: runtime skeleton → persistence → graph → memory svc → locks/Git → MCP → router → UI → E2E → deploy
IDE client (000O): bootstrap → locks → patch/apply → agent workflow (100K–100N), same backend authority
```

**Orchestration (000P — Nike):** **000P** defines Nike as the internal event-routing layer between producers (API, UI, IDE, worker, MCP, router, locks) and LangGraph/runtime consumers; product behavior is implemented under **100O**, placed after **100C** in §2–§3. Nike sits **after** the API in the **canonical processing chain** (see “Backend as work-processing authority” above); the API ingests; the worker runs the default Nike dispatcher (**100O**).

**Components:** `trident-api` (control + APIs), `trident-worker` (async jobs), `trident-exec` (MCP broker), `trident-web` (control plane UI), optional **Code-OSS IDE** client via extension/bridge—all agree on backend state (see `000O`, `100A` layout).

---

## 2. Canonical Build Order

```text
START HERE

Phase 1 — Core platform:
100A → 100B → 100C → 100O → 100D → 100E → 100F → 100G → 100H → 100I → 100J

Phase 2 — IDE (after Phase 1 prerequisites; see §4):
100K → 100L → 100M → 100N
```

**Design authority:** LLD directives **000A–000P** (including **000P — Nike**) and **Manifest v1.0** must be accepted before code tracks **100A+**. **Fix directives 001–005** apply at the injection points in §5—not optional patches.

---

## 3. Inline Dependencies (Implementation Directives)

Each row lists **prior implementation steps**, **design directives (LLD)** that define acceptance for that phase, and **minimum system state** before starting.

| Step | Requires (implementation) | LLD / manifest gate | Required system state |
|------|---------------------------|---------------------|------------------------|
| **100A** Repository + runtime skeleton | — | **000A–000P**, Manifest | Approved architecture; repo writable; containers definable |
| **100B** Schema + persistence | 100A | **000A**, **000B**, **000D**, **000K**, **000L** | Skeleton runs; DB/vector placeholders exist |
| **100C** LangGraph spine | 100B | **000B**, **000D** | Schemas persist; ledger model bindable |
| **100O** Nike event orchestrator (implementation) | 100C | **000P** | LangGraph spine proven; graph is authoritative for workflow |
| **100D** Memory system | **100O** | **000C** | Nike routing available per **000P**; graph runs |
| **100E** Git + file lock | 100D | **000E** | Memory APIs stable for audit/events |
| **100F** MCP execution | 100E | **000F** | Locks + repo governance operational |
| **100G** Router | 100F | **000G** | MCP receipts + execution path proven |
| **100H** UI | 100G | **000H** | Router decisions observable server-side |
| **100I** End-to-end validation | 100H | **000I** | UI reflects backend truth (no mock-as-proof) |
| **100J** Deployment + production validation | 100I | **000J**, **000M** | Full lifecycle test path exists |
| **100K** IDE bootstrap | **100H** | **000O** | Web control plane usable; API stable for IDE |
| **100L** IDE file lock + governed edit | 100K | **000O** | IDE connects to backend project/registry |
| **100M** Patch / apply workflow | 100L | **000O** | Governed edit path exists |
| **100N** IDE agent workflow | 100M | **000O** | Patch pipeline + MCP surfacing ready |

**Unlock chain (next step only when current phase meets its directive’s acceptance criteria):**  
100A → 100B → 100C → 100O → 100D → 100E → 100F → 100G → 100H → 100I → 100J; then 100K → 100L → 100M → 100N.

### 3.1 Locating implementation directive files

Each step’s authoritative scope and proof live in the repo as Markdown files matching:

```text
TRIDENT_IMPLEMENTATION_DIRECTIVE_<STEP>_<TITLE_SLUG>.md
```

**Example — 100A:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100A_REPOSITORY_RUNTIME_SKELETON.md`  
**Example — 100O:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100O_NIKE_EVENT_ORCHESTRATOR.md` — Nike implementation per **000P** (worker dispatcher; backend agent-hook extensibility per Manifest §2 principles 12–13).  
Fix directives: under `TRIDENT_FIX_DIRECTIVES_001_005/` or matching `TRIDENT_FIX_DIRECTIVE_<NNN>_*.md`.

---

## 4. Phase 2 (IDE) Prerequisite

Do **not** start **100K** until **100H** is complete (implementation dependency) and **000O** is the governing IDE architecture reference.

---

## 5. Fix Directive Injection Points

Apply **FIX 001–005** at the following gates. Details remain in each fix document—this section only fixes **when** they bind to the spine.

| Fix | Complete after | Complete before | Notes |
|-----|----------------|-----------------|--------|
| **FIX 004** — Memory consistency / transaction model | **100D** | **100G**, **100I** | Aligns structured + vector + ledger semantics before router and full integration rely on retrieval. |
| **FIX 005** — Router confidence + escalation guard | **100G** | Relying on **production external API** routing | Depends on **000G** + router implementation. |
| **FIX 002** — Git commit governance | **100E** | **100I**, **100J** | Needs Git/file-lock implementation; finish before E2E and deploy validation that assume drift detection. |
| **FIX 001** — IDE write gate | **100K**, **100L** | **100M**, **100N** | Governed IDE edits before patch/agent workflows. |
| **FIX 003** — Lock heartbeat + expiry | **100L** (with **100E** foundation) | **100M**, **100N** | Stale-lock behavior before patch/apply and IDE agent flows. |

**Suggested ordering within the spine (fixes shown inline):**

```text
100A → 100B → 100C → 100O → 100D
  → FIX 004
  → 100E → 100F → 100G
  → FIX 005 (before prod external routing)
  → 100H
  → FIX 002 (must complete before 100I)
  → 100I → 100J

100K → 100L
  → FIX 001
  → FIX 003
  → 100M → 100N
```

If **FIX 001** and **FIX 003** share touchpoints (locks + IDE), they may be executed in parallel once **100L** is satisfied; both must finish before **100M**.

---

## 6. Execution Rules

- **No skipping phases** in §2 unless a written architecture change updates this guide and the manifest.
- **No parallel implementation** of layers that share enforcement boundaries (e.g. UI feature work before backend state exists for that feature)—follow **000K** discipline.
- **No agents, tools, memory writes, file mutation, or product execution paths** outside **LangGraph**, **MCP**, and **Git/lock** rules defined in the Manifest and **000K §15**, *except as qualified below*.
- **Directive-required engineering commands:** Execution rules **do not** block commands **required by the active directive** for build, test, validation, or scaffolding. Examples when specified in the directive: `docker compose` (build/up/ps), `curl` to `/api/*` health endpoints, `pytest` / test runners, filesystem operations needed to create the scaffold. **Rule:** If the directive requires it, it is allowed — including under enforcement rules — provided it does not smuggle in product MCP/SSH/shell behavior ahead of the phased rollout.

---

## 6a. Enforcement vs directive-required tooling

| Category | Meaning |
|----------|---------|
| **Product runtime** | Agents, MCP brokers, SSH/shell execution as Trident features — phased per directives; not improvised in skeleton phases. |
| **Engineering tooling** | Commands explicitly listed in the directive’s validation/tests/proof sections — **always allowed** when executing that directive. |

---

## 7. Anti-Drift Rules

- **Backend** is the source of truth for projects, directives, ledger, memory, locks, execution receipts, and router logs.
- **No IDE bypass** of locks, write gates, or Git policy for governed projects.
- **No product/runtime execution** outside the MCP layer when implementing governed execution — **not** a ban on directive-required **engineering commands** (see **§6a**).
- **No ungoverned file edits** to tracked project paths where directives apply (scaffolding per active directive is governed by that directive).
- **No memory writes** except through LangGraph-governed paths when those phases are in scope (**000C** / **100C–100D**).

---

## 8. Completion Criteria per Phase

Abbreviated summary only; **acceptance and proof follow the implementation directive first**, then this table as a cross-check.

| Phase | Done means | Proof (examples) | Blocks if missing |
|-------|------------|------------------|-------------------|
| **100A** | All services start; health/version endpoints | Container logs, `/api/health` | Cannot persist schemas |
| **100B** | Models + migrations + validation tests | Failing tests on invalid payloads | Cannot bind LangGraph state safely |
| **100C** | Graph runs end-to-end test directive | Trace + ledger transitions | Memory/router/UI invalid |
| **100O** | Nike orchestration per **000P** | Event routing proofs + no bypass of LangGraph | **100D** blocked |
| **100D** | Read/write APIs + scoped retrieval | Persistence across restart | Locks/Git meaningless |
| **100E** | Acquire/release lock; repo state captured | Conflict + audit logs | MCP/file ops unsafe |
| **100F** | MCP-only execution path; approvals | Receipts in ledger/memory | Router/UI disconnected |
| **100G** | Local-first routing + logged escalation | Decision logs | UI lies about routing |
| **100H** | Panels bind to real APIs | No mock backend state | **100I** blocked |
| **100I** | E2E lifecycle + failure tests | Full audit trail | **100J** blocked |
| **100J** | Deploy checklist + prod validation | Install/backup/health proof | Production approval |
| **100K–100N** | IDE milestones per directive | IDE + API proofs per **100K–100N** | “Cursor-equivalent” IDE incomplete |

**Fix directives:** each FIX’s §5–7 acceptance, tests, and proof objects apply at its injection gate.

---

## 9. How to Use This Document

1. Follow **Policy — Onboarding read scope**: Master Guide (relevant sections), Playbook, target directive file, and **only LLDs/parents that directive lists** — not full **000A–000P** pre-read.  
2. Execute **Phase 1** in order; apply **§5** fixes at the listed gates.  
3. Complete **100H**, then **Phase 2** IDE sequence with **FIX 001** and **FIX 003** before **100M**.  
4. Resolve conflicts using **Policy — Source of truth**: **implementation directive → this guide → playbook**; LLD details win over this guide where the directive points to them.  
5. Use **`TRIDENT_GOVERNED_EXECUTION_PLAYBOOK_v1_1.md`** for the mandatory **Read → Plan → Build → Prove → Review** loop on each directive (no coding until plan acknowledgment; proof before next step).

---

## 10. Example Walkthrough (New Engineer)

1. Read **Policy**, **§2** (order), and **§3** row for the next step; open **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100A_…`** and only the LLDs listed there if starting **100A**.  
2. Build skeleton per **100A** until directive acceptance; checkpoint.  
3. Follow **100B → 100C → 100O → 100D** using each directive’s acceptance criteria (**100O** implementation directive issued; see filename under §3.1).  
4. After **100D** passes, open **FIX 004**; implement and prove before **100G**.  
5. Continue **100E → 100F → 100G**; implement **FIX 005** before treating external APIs as production-ready.  
6. Complete **100H**; implement **FIX 002** before **100I**.  
7. Run **100I → 100J**; then **100K → 100L**; apply **FIX 001** and **FIX 003**; finish **100M → 100N**.

---

## 11. Validation Notes (Test Reader Checklist)

- [ ] Next step after each phase is unique and matches §2–5.  
- [ ] Every **100x** row in §3 matches its directive **Manifest Link**.  
- [ ] **FIX 001–005** appear exactly once at the correct gate.  
- [ ] No new behavioral requirements beyond orchestration (per **FIX 006 §5**).

---

## 12. Document Control

| Item | Value |
|------|--------|
| Issued under | **TRIDENT FIX DIRECTIVE 006** |
| Supersedes | Informal build order only |
| Next review | When Manifest or **100x** chain changes |

---

END OF DOCUMENT
