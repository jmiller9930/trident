# Project Trident — Document Manifest v1.0

**Document Type:** Canonical Manifest / Document Control Index  
**Project:** Trident  
**Status:** Active Architecture Control Document  
**Owner:** Chief Architect  
**Created:** 2026-04-29  
**Purpose:** Track every Trident architecture and directive document, enforce ordering, prevent orphan documents, and ensure each body of work links back to the master plan before engineering implementation begins.

---

## 1. Manifest Rule

Every Trident document must link back to this manifest.

No architecture document, LLD directive, implementation directive, proof package, or handoff record is valid unless it includes manifest metadata.

Required metadata block for every document:

```yaml
manifest_id: TRIDENT-MANIFEST-v1.0
project: Project Trident
parent_document: TRIDENT_DOCUMENT_MANIFEST_v1_0.md
document_id: <unique document id>
document_type: <HLD | LLD | Directive | Proof | Handoff | Review>
sequence: <ordered position>
status: <Draft | Active | Superseded | Closed>
dependencies: []
produces: []
langgraph_required: true
```

---

## 2. Locked Architecture Principles

Trident is a memory-first, multi-agent, local-first AI software delivery control plane.

The system is governed by these non-negotiable principles:

1. LangGraph is mandatory for multi-agent workflow enforcement.
2. LangChain may be used for tools, retrieval, prompts, loaders, and model adapters.
3. No agent may perform meaningful project work outside a governed LangGraph workflow.
4. Agent roles are graph nodes.
5. Task lifecycle transitions occur through graph state.
6. Memory reads and writes occur through graph-governed execution.
7. Agent handoffs and acknowledgments are durable records.
8. MCP is the execution/tool access layer.
9. Git and file locking are mandatory for mutation.
10. Proof objects are required for closure.
11. The UI must expose real workflow, memory, Git, lock, execution, and proof state.
12. **The backend is the work-processing authority.** The IDE is a Cursor-style frontend/editor surface; the web UI is a control-plane frontend. **Agent workflows** must run through **backend-governed** services — **not** as independent IDE-side execution. Canonical processing chain:

    ```text
    IDE / Web → API → Nike → LangGraph → Agents / Memory / SubsystemRouter (100G) / MCP / Proof
    ```

    *(**Subsystem Router** = **100G** — MCP / LangGraph / Nike / memory-read routing only. **Model Router** = **100R** governed by LLD **000G** — LLM local/external escalation; separate directive.)*

    Git and file-lock governance applies on governed mutation paths; it does not replace this chain.

13. **Nike and event routing** must be designed so **future backend-managed agent types** can be added **without redesign** of the API → Nike → LangGraph spine. Minimum named hooks (graph nodes, events, or server-side handlers — not IDE-local orchestrators): **Engineer agent**, **Reviewer agent**, **Documentation agent**, **Debugger agent**, **Test agent**, **Security review agent**, **Performance review agent**, **Deployment/release agent**. Details: **Master Execution Guide §1**, **000P §3.3**, **100O** implementation alignment.

14. **Model cadre (architecture — implementation in 100R):** Trident must **not** assume all agents share one LLM. The product SHALL support a configurable **model cadre**:

    ```text
    SINGLE_MODEL_MODE:
      all agents use the same configured local model

    CADRE_MODE:
      each agent role may have its own assigned model profile
    ```

    **Required role → profile mapping (conceptual):** Architect → reasoning; Engineer → coding; Reviewer → validation/review; Debugger → diagnostic/code-fix; Docs → documentation/summarization. **External OpenAI/API models are fallback only**, not the default execution path. **Hardware planning target:** RTX 6000–class GPU, **32GB VRAM**; **local-first** runtime. **Provisional model names** are candidates until **100R** benchmarks and health checks validate fit — do not treat them as locked production choices. **100I** validates only that the **current design does not block** future per-agent assignment; **100I does not implement** model routing.     **100R** owns registry, per-agent assignment, both modes, local-first routing, external fallback policy, fallback-reason logging, token/cost logging, model health checks, and VRAM-fit validation. Model routing MUST NOT be implemented in Nike, MCP, or the IDE.

15. **Product blueprint (`APP_BLUEPRINT_001`):** The canonical **product** architecture for forward UX, gates, and enforcement is documented in **`trident/docs/APP_BLUEPRINT_001.md`** (addenda: Model Readiness + Agent Brain Assignment; RAG / shared context; VS Code Workbench UI + governed development loop; project type → architecture → canonical structure; **prerequisites / environment readiness**; **environment governance**; **state engine**). Engineering must treat this file as the **single product blueprint** alongside LLDs and implementation directives. **Program acceptance** of blueprint addenda (**STATE_ENGINE**, **PREREQUISITES**) is recorded in **`trident/docs/WORKFLOW_LOG.md`** and receipt rows in **`trident/docs/DIRECTIVE_WORKFLOW_LOG.md`** — update manifest status lines when program signs.

---

## 2.1 Product blueprint registry (APP_BLUEPRINT_001)

#### TRIDENT-PRODUCT-BLUEPRINT-APP_BLUEPRINT_001
**File:** `trident/docs/APP_BLUEPRINT_001.md`  
**Type:** Product blueprint (HLD-level product contract — **unified single document**)  
**Status:** **Canonical product blueprint** — **`APP_BLUEPRINT_001_UNIFIED_REWRITE`** (**ISSUED** / content **READY**); prior append-only addenda **superseded** by unified §§1–15 in-file  
**Purpose:** End-to-end product model: backend-authoritative workspace/project; thin VS Code client; **shared chat** + **`#architect`** intake; collaboration roles; normalization pipeline; **project-scoped RAG** (no cross-project/global fallback); **state machine**; structure/scaffold rules; **environment governance**; **model cadre readiness**; patch/proof/bug-check loops; **§13 API gap** inventory.  
**Depends on:** Manifest principles §2; **`APP_LLD_001`** (**ACCEPTED**) for engineering decomposition.  
**Produces:** Contracts for implementation directives and API completion.

#### TRIDENT-IMPLEMENTATION-DESIGN-APP_IMPLEMENTATION_DESIGN_001
**File:** `trident/docs/APP_IMPLEMENTATION_DESIGN_001.md`  
**Type:** System implementation design (technical — services, data, APIs, state machine, RAG, intake, UI contract)  
**Status:** **ISSUED** / document **READY**  
**Purpose:** Translates **`APP_BLUEPRINT_001`** into **implementable** boundaries without restating product prose; defines concrete tables (**+** net-new), endpoint matrix, state transition discipline, context isolation guarantees.  
**Depends on:** **`APP_BLUEPRINT_001`** (unified); **`APP_LLD_001`**; codebase **`STATE_001`**.  
**Produces:** Build-ready specs for implementation directives and engineering execution.

#### TRIDENT-IMPLEMENTATION-DESIGN-REVIEW-APP_IMPLEMENTATION_DESIGN_001_REVIEW
**File:** `trident/docs/APP_IMPLEMENTATION_DESIGN_001_REVIEW.md`  
**Type:** Engineering validation / build-authorization input  
**Status:** **ISSUED** / **READY**  
**Purpose:** Validates **`APP_IMPLEMENTATION_DESIGN_001`** against **`APP_BLUEPRINT_001`**; gap closure rules; cross-system consistency; failure modes; **READY_FOR_IMPLEMENTATION** with controlled sequencing — **no code**.  

#### Blueprint addenda — acceptance tracking
| Addendum | Role | Program status |
|----------|------|----------------|
| **`APP_BLUEPRINT_STATE_ENGINE_ADDENDUM`** | Enforcement layer: gates, transitions, UI aggregates, LangGraph/Nike integration | **ACCEPTED** — recorded **`trident/docs/WORKFLOW_LOG.md`** (`DOC_APP_BLUEPRINT_ALIGNMENT`) |
| **`APP_BLUEPRINT_PREREQUISITES_ADDENDUM`** | Prerequisites / environment readiness checklist | **ACCEPTED** — recorded **`WORKFLOW_LOG.md`** (`DOC_APP_BLUEPRINT_ALIGNMENT`) |

#### TRIDENT-LLD-APP_LLD_001
**File:** `trident/docs/APP_LLD_001.md`  
**Type:** LLD (post-blueprint engineering decomposition)  
**Status:** **ACCEPTED** — program **2026-04-30**; implementation via issued directives (**STATE_001** first)  
**Purpose:** Epics **E01–E10**, numbered implementation directives (**WB_***, **THR_***, **STATE_***, **GATE_***, **PROJ_***, **RAG_***, **MODEL_***, **PATCH_***, **PROOF_***, **QA_***), strict phased **build order**, dependency graph; aligns blueprint with state engine, gates, env governance, UI, RAG, cadre, agents, patch, proof, QA.  
**Depends on:** **`APP_BLUEPRINT_001`** (accepted); blueprint addenda **ACCEPTED** per **`WORKFLOW_LOG.md`**.  
**Produces:** Scoped **`TRIDENT_IMPLEMENTATION_DIRECTIVE_*`** issuance targets.  
**Pointer:** `trident/docs/APP_LLD_001_PLAN.md` → canonical **`APP_LLD_001.md`**.

---

## 3. Canonical Document Sequence

### Foundation Layer

#### TRIDENT-FOUNDATION-v1.0
**File:** `docs/archive/trident_foundation_v1_0.md`  
**Type:** HLD + LLD foundation  
**Status:** Archived baseline (v1.1 is canonical in Master Execution Guide)  
**Purpose:** Defines Trident identity, memory-first architecture, multi-agent workflow, protocol stack, and high-level system boundaries.  
**Depends on:** Original Project Trident design documentation PDF  
**Produces:** Foundation for all LLD directives.

#### TRIDENT-HLD-UI-v1.2
**File:** To be issued / may be merged into next HLD revision  
**Type:** HLD addition  
**Status:** Required  
**Purpose:** Locks web UI, Cursor-like interaction model, multi-user control plane, LangGraph visualization, memory visibility, Git panel, file locks, proof panel, and approval UX.

---

### LLD Directive Layer

#### TRIDENT-DIRECTIVE-000A
**File:** `TRIDENT_DIRECTIVE_000A_SCHEMAS_AND_GRAPH_CONTRACTS.md`  
**Type:** LLD Directive  
**Status:** Active  
**Purpose:** Defines directive schema, handoff schema, proof object schema, memory record schema, and LangGraph contract foundation.  
**Depends on:** TRIDENT-FOUNDATION-v1.0  
**Produces:** Schema language for subsequent directives.

#### TRIDENT-DIRECTIVE-000B
**File:** `TRIDENT_DIRECTIVE_000B_TASK_LEDGER_AND_LANGGRAPH_STATE_MACHINE.md`  
**Type:** LLD Directive  
**Status:** Issued  
**Purpose:** Defines the task ledger, source-of-truth state machine, LangGraph runtime binding, ownership, acknowledgments, rejection loops, failure states, and state persistence rules.  
**Depends on:** TRIDENT-DIRECTIVE-000A  
**Produces:** Runtime state model required before memory, agents, UI, Git, and execution can be implemented.

#### TRIDENT-DIRECTIVE-000C
**File:** Pending  
**Type:** LLD Directive  
**Status:** Planned  
**Purpose:** Memory system: structured memory, vector memory, project memory, task memory, role-scoped views, retrieval rules, and blackboard persistence.

#### TRIDENT-DIRECTIVE-000D
**File:** Pending  
**Type:** LLD Directive  
**Status:** Planned  
**Purpose:** Agent contracts: Architect, Engineer, Reviewer, Documentation, optional Operator, exact inputs/outputs, authority boundaries, and validation obligations.

#### TRIDENT-DIRECTIVE-000E
**File:** Pending  
**Type:** LLD Directive  
**Status:** Planned  
**Purpose:** Git governance and file locking: repo validation, dirty-tree handling, branch policy, lock acquisition, conflict prevention, diff handling, commit gates, rollback rules.

#### TRIDENT-DIRECTIVE-000F
**File:** Pending  
**Type:** LLD Directive  
**Status:** Planned  
**Purpose:** MCP execution layer: SSH, shell, vCenter, Docker, command classification, approval gates, execution receipts, safety policies.

#### TRIDENT-DIRECTIVE-000G
**File:** `TRIDENT_DIRECTIVE_000G_ROUTER_POLICY.md`  
**Type:** LLD Directive  
**Status:** Issued (policy); implementation deferred to **100R**  
**Purpose:** **Model-router** policy only: local-first LLM routing, external API fallback, cost awareness, escalation rules, model selection, traceability. **Does not** define **100G** subsystem/work-request routing (see **100G** implementation directive).

#### TRIDENT-DIRECTIVE-000H
**File:** Pending  
**Type:** LLD Directive  
**Status:** Planned  
**Purpose:** UI state binding: maps LangGraph, task ledger, memory, Git, file locks, proof, approvals, and execution queues to the web interface.

#### TRIDENT-DIRECTIVE-000P
**File:** `TRIDENT_DIRECTIVE_000P_NIKE_EVENT_ORCHESTRATOR.md`  
**Type:** LLD Directive  
**Status:** Issued  
**Purpose:** Nike Event Orchestrator — non-intelligent event routing and workflow coordination between API/UI/IDE producers and LangGraph/runtime consumers (per directive).  
**Depends on:** TRIDENT-DIRECTIVE-000B (and prerequisite foundation/directives cited in 000P).  
**Produces:** Nike orchestration contract for implementation directive **100O**.

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100O
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100O_NIKE_EVENT_ORCHESTRATOR.md`  
**Type:** Implementation Directive  
**Status:** Issued  
**Purpose:** Implement Nike per **000P** (worker dispatcher, ingest API, persistence, LangGraph wakeup boundary). Sequenced after **100C**, before **100D**. Must preserve backend agent-hook extensibility per principles 12–13.

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100G
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100G_ROUTER.md`  
**Type:** Implementation Directive  
**Status:** Issued  
**Purpose:** **Subsystem / work-request router** — routes intent to **MCP**, **LANGGRAPH**, **NIKE**, or **MEMORY** (read). Pure decision layer; **no** LLM selection, **no** execution, **no** MCP risk classification.  
**Depends on:** **100F**  
**Unlocks:** **100H** — Agent Execution Layer (backend; not UI)

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100H
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100H_AGENT_EXECUTION_LAYER.md`  
**Type:** Implementation Directive  
**Status:** Issued  
**Purpose:** **Agent Execution Layer (backend)** — governed agent work through LangGraph → MCP → receipts → memory/audit; **no UI responsibilities.**  
**Depends on:** **100G**  
**Unlocks:** **100I**

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100I
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100I_END_TO_END_VALIDATION.md`  
**Type:** Implementation Directive  
**Status:** Issued  
**Purpose:** **End-to-end system validation** — full lifecycle proof on real stack (e.g. Postgres + compose); **no** LLM/model-router implementation (**100R**). Must confirm architecture does **not** obstruct future **model cadre** / per-agent profiles (see principle **§2.14**, **000G**, **100R**).  
**Depends on:** **100H**  
**Unlocks:** **100J**

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100J
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100J_DEPLOYMENT_PRODUCTION_VALIDATION.md`  
**Type:** Implementation Directive  
**Status:** Issued  
**Purpose:** **Deployment + production validation** — compose deploy, health, restart durability, persistence, baseline security/logging/runbook; **no** new product features (**000J**, **000M**).  
**Depends on:** **100I**  
**Unlocks:** **100L**

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100L
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100L_PRODUCTION_HARDENING.md`  
**Type:** Implementation Directive  
**Status:** Issued  
**Purpose:** **Production readiness & operational hardening** — compose stability (restart, limits, ordering), failure handling (DB, Chroma, worker bounds), observability, security baseline, backup/restore, operational runbooks; **no** features, **no** architecture or agent/router/MCP changes, **no** **100R**.  
**Depends on:** **100J**  
**Unlocks:** **100U**

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100U
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100U_UI.md`  
**Type:** Implementation Directive  
**Status:** Issued  
**Purpose:** Web UI — LangGraph + system state visualization; real backend binding per **000H**.  
**Depends on:** **100L**  
**Unlocks:** **100K**

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100R
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100R_MODEL_ROUTER_LOCAL_FIRST.md`  
**Type:** Implementation Directive  
**Status:** Issued — **Deferred** (program-scheduled after **100G**; **model cadre** and per-agent profiles fully specified there)  
**Purpose:** **Model router** — local-first LLM vs external API escalation per **000G**; **SINGLE_MODEL_MODE** and **CADRE_MODE**; model profile registry; per-agent assignment; fallback reason + token/cost logging; health checks and benchmark validation for **32GB-class** local targets. Former LLM-router content incorrectly filed as **100G**; relocated here.  
**Depends on:** **100G**, **100F**, **000G**

---

## 4. Document Issuance Rule

Each directive must be issued as a separate Markdown document.

Each document must:

1. Include the required manifest metadata block.
2. Reference its parent and dependencies.
3. Define what it produces.
4. State what engineering is authorized and not authorized to build.
5. Include acceptance criteria.
6. Include proof requirements.
7. Declare LangGraph enforcement where relevant.
8. End with the next expected document.

---

## 5. Current Next Document

### 5.1 Forward path (post–product-blueprint)

After **`APP_BLUEPRINT_001`** is **accepted as product blueprint** (program log: **`WORKFLOW_LOG.md`** — `DOC_APP_BLUEPRINT_ALIGNMENT`):

```text
APP_BLUEPRINT_001 → LLD (e.g. APP_LLD_001) → EPICS → IMPLEMENTATION DIRECTIVES
```

- **LLD document:** `trident/docs/APP_LLD_001.md` — **APP_LLD_001** (**ACCEPTED** program **2026-04-30**); pointer `trident/docs/APP_LLD_001_PLAN.md`.  
- **Implementation** for blueprint-scoped work proceeds under **issued implementation directives** (see **Master Execution Guide v1.1 §2.1**). **STATE_001** — state schema foundation — **ISSUED / READY** per `STATE_001_PLAN.md`.

Update this subsection when **`APP_LLD_001`** is superseded by a revised LLD revision id.

### 5.2 Foundation LLD sequence (design corpus)

The next document in the **traditional** LLD sequence after **000B** remains:

**TRIDENT-DIRECTIVE-000C — Memory System and Blackboard Architecture**

Do not issue implementation code that depends on missing **000C–000H** acceptance without explicit program waiver. The product blueprint does **not** replace foundational LLDs; it **aligns** product UX and enforcement with them.

---

## 6. Directive Registry and Naming Standard (added 2026-05-01)

**Canonical directive registry:** `trident/docs/TRIDENT_DIRECTIVE_REGISTRY.md`

### Naming standard (effective 2026-05-01)

```
TRIDENT_<DOMAIN>_<SEQUENCE>
```

Old-style `TRIDENT_IMPLEMENTATION_DIRECTIVE_*` names are **deprecated** but **retained as historical aliases** and must never be erased.

### Implemented directive family (backfilled 2026-05-01)

| Canonical | Domain | Status | Migration |
|-----------|--------|--------|-----------|
| `TRIDENT_IMPL_001` | Control plane | PASS / ACCEPTED | `impl001001` |
| `TRIDENT_MODEL_ROUTER_001` | Model plane wiring | PASS / ACCEPTED | _(settings only)_ |
| `TRIDENT_MODEL_ROUTER_002` | Model plane wiring | PASS / ACCEPTED | _(settings only)_ |
| `TRIDENT_ONBOARD_001` | Onboarding schema | PASS / ACCEPTED | `onboard001001` |
| `TRIDENT_ONBOARD_002` | Onboarding scan | PASS / ACCEPTED | _(service only)_ |
| `TRIDENT_GITHUB_001` | GitHub provider | PASS / ACCEPTED | _(service only)_ |
| `TRIDENT_GITHUB_002` | GitHub schema | PASS / ACCEPTED | `github002001` |
| `TRIDENT_GITHUB_003` | GitHub API | PASS / ACCEPTED | _(service only)_ |
| `TRIDENT_GITHUB_004` | GitHub directive branch | PASS / ACCEPTED | _(service only)_ |
| `TRIDENT_GITHUB_005` | GitHub commit push | PASS / ACCEPTED | _(service only)_ |
| `TRIDENT_PATCH_001` | Patch proposals | PASS / ACCEPTED | `patch001001` |
| `TRIDENT_PATCH_002` | Patch execution | PASS / ACCEPTED | `patch002001` |
| `TRIDENT_VALIDATION_001` | Validation tracking | PASS / ACCEPTED | `valid001001` |
| `TRIDENT_SIGNOFF_001` | Sign-off + closure | PASS / ACCEPTED | `signoff001001` |
| `TRIDENT_STATUS_001` | Execution state | PASS / ACCEPTED | _(read-only)_ |
| `TRIDENT_VSCODE_001` | VS Code extension | PASS / ACCEPTED | _(TS only)_ |
| `TRIDENT_REGISTRY_CLEANUP_001` | Registry docs | PASS | _(docs only)_ |

**Current migration head:** `signoff001001`  
**Current test suite:** 404 passed, 3 skipped (2026-05-01)
