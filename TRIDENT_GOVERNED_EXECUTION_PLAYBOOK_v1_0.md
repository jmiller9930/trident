# Project Trident — Governed Execution Playbook v1.0

**Document Type:** Operational process / Sequential build + proof gates  
**Project:** Trident  
**Status:** Active  
**Purpose:** Single repeatable process engineering uses to execute Trident **one directive at a time**, with proof at each gate before advancing.

```yaml
manifest_id: TRIDENT-MANIFEST-v1.0
project: Project Trident
parent_document: TRIDENT_DOCUMENT_MANIFEST_v1_0.md
document_id: TRIDENT-GOVERNED-EXECUTION-PLAYBOOK-v1.0
document_type: Handoff
sequence: PLAYBOOK-v1.0
status: Active
dependencies:
  - TRIDENT-MASTER-EXECUTION-GUIDE-v1.0
  - TRIDENT-FIX-006-MASTER-EXECUTION-GUIDE
langgraph_required: true
```

**Relationship:** This playbook is the **only** progression model for implementation. **`TRIDENT_MASTER_EXECUTION_GUIDE_v1_0.md`** holds dependency order and fix-injection timing; this document defines **how** each step is executed and proven.

**Source of truth (scope and proof):**

```text
Implementation Directive → Master Execution Guide → Governed Execution Playbook
```

This playbook does **not** define feature scope, proof lists, or acceptance criteria — those come from the **target directive** first.

---

## Purpose

Provide one repeatable process: **Read → Plan → Build → Prove → Review → Accept → Next**. Work advances **one directive per cycle** unless leadership explicitly authorizes parallel tracks.

---

## Operating Model

```text
One Directive → Build → Prove → Review → Accept → Next
```

- No batching multiple directives in one cycle without authorization.
- No parallel tracks unless explicitly authorized.

---

## Start Condition (BLOCKING)

Before **any** implementation build:

1. **FIX 006 — Master Execution Guide** is complete (master guide exists and is accepted).
2. Submit:
   - `TRIDENT_MASTER_EXECUTION_GUIDE_v1_0.md`
   - Evidence that a **new engineer** can follow it (walkthrough / validation notes — see Master Guide §10–11).

**Implementation starts only after this is accepted.**

---

## Execution Loop (repeat for every directive)

### Step 1 — Read

**Before coding:**

- **Master Execution Guide** — sections for the next step (order, §3 dependencies, §5 fix gates when relevant).
- **This playbook** — execution loop and templates.
- **Target implementation or fix directive** (e.g. `TRIDENT_IMPLEMENTATION_DIRECTIVE_100A_…`).
- **LLDs and parents that directive explicitly references** (e.g. “Parent Architecture References” / listed foundation — **header-level references only**).

**Not required:** Pre-reading the full **000A–000N** corpus.

Read **Fix** directives only when **Master Execution Guide §5** says this step is at an injection gate, or when implementing that fix.

Rule: **Read only what the target directive explicitly references** (plus Master Guide sections above). No broad pre-reading required.

### Step 2 — Confirm Plan

Return a short plan using this template:

```text id="planblk"
Directive: <ID>
Plan:
- What will be built
- Dependencies confirmed
- Risks noted
```

**Do not start coding until this plan is acknowledged.**

### Step 3 — Build

- Implement **only** the scope of the directive.
- Respect all constraints (LangGraph, MCP, locks, router, memory, Git, etc.).
- No extra features.

### Step 4 — Prove (MANDATORY)

Return every proof object **required by the target directive** (authoritative). Use at least the playbook structure below for packaging:

```text id="proofblk"
Directive: <ID>
Status: PASS | FAIL | PARTIAL
Commit:
Files Changed:
Commands Run:
Test Output:
Proof Objects:
- logs
- API outputs
- screenshots (if UI)
- persistence/restart proof
Known Gaps:
```

### Step 5 — Review Gate

Reviewers will:

- Validate against the **implementation or fix directive** first (then Master Guide alignment).
- Check for bypasses (LangGraph / MCP / locks / router / memory rules).
- Verify proofs are **real** (no mock state passed off as backend truth).

Outcome:

```text id="gateblk"
ACCEPTED → proceed to next directive
REJECTED → fix and resubmit
```

---

## Directive Order (authoritative)

### Control plane spine

```text
100A → 100B → 100C → 100O → 100D → 100E → 100F → 100G → 100H → 100I → 100J → 100U
```

### IDE track (after **100U** + **`000O`** prerequisites per Master Guide v1.1)

```text
100K → 100P → 100M → 100N
```

### Fix directives

Apply **only** at injection points defined in **`TRIDENT_MASTER_EXECUTION_GUIDE_v1_1.md`** (§5) — **v1.1 is authoritative** for fix gates:

| Fix   | Placement (summary)                          |
|-------|-----------------------------------------------|
| FIX 001 | Before **100M** / **100N**                  |
| FIX 002 | Before **100I** / **100J**                  |
| FIX 003 | Before **100M** / **100N**                  |
| FIX 004 | Before **100G** / **100I**                  |
| FIX 005 | After **100R** (before production **external LLM API** reliance) |

Exact “complete after / before” gates live in the Master Execution Guide.

---

## Hard Rules (non-negotiable)

Subject to **Implementation Directive → Master Execution Guide → Playbook** priority. Directive-required engineering commands (`docker compose`, `curl` to health endpoints, `pytest`, scaffold filesystem ops, etc.) are **allowed when specified in the active directive** — they are not optional shortcuts; see Master Guide **§6 / §6a**.

- No **product** agent/workflow execution outside **LangGraph** (when that phase is in scope per directive).
- No **product** tool/command execution outside **MCP** when implementing MCP-governed behavior (directive-defined).
- No file mutation without **Git + lock** validation **when the directive for that phase requires it**.
- No memory writes outside **graph nodes** when memory/LangGraph phases apply (per active directive).
- No external API calls without **router decision + logging** when router phases apply (per active directive).
- No UI mock state used as proof.
- No skipping directives.

**Process:** No coding until **Step 2** plan acknowledgment; no advancing until proof matches the **directive**.

---

## Stop Conditions

Stop immediately and report if:

- A dependency is missing or unclear.
- Directives conflict.
- Enforcement (LangGraph / MCP / locks / router / memory) cannot be guaranteed for the proposed scope.
- Required proof cannot be produced.

---

## Anti-drift

- Backend is the source of truth.
- IDE cannot bypass backend governance.
- Git drift must be detected and handled (see FIX 002 when scheduled).
- Locks must be enforced and visible.
- Actions must be auditable.

---

## Completion

The system is complete only when:

- **100A–100J** and **100K–100N** are **accepted** under this playbook.
- All **Fix** directives are **implemented at the correct injection points**.
- **100I** (end-to-end validation) passes.
- **100J** (deployment / production validation) passes.

---

END OF PLAYBOOK
