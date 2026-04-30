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

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100U
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100U_UI.md`  
**Type:** Implementation Directive  
**Status:** Issued  
**Purpose:** Web UI — LangGraph + system state visualization; real backend binding per **000H**.  
**Depends on:** **100J**  
**Unlocks:** **100K**

#### TRIDENT-IMPLEMENTATION-DIRECTIVE-100R
**File:** `TRIDENT_IMPLEMENTATION_DIRECTIVE_100R_MODEL_ROUTER_LOCAL_FIRST.md`  
**Type:** Implementation Directive  
**Status:** Issued — **Deferred** (program-scheduled after **100G**)  
**Purpose:** **Model router** — local-first LLM vs external API escalation per **000G**. Former content incorrectly filed as **100G**; relocated here.  
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

The next document after this manifest and Directive 000B is:

**TRIDENT-DIRECTIVE-000C — Memory System and Blackboard Architecture**

Do not issue implementation code before 000C, 000D, 000E, 000F, 000G, and 000H are completed and accepted.
