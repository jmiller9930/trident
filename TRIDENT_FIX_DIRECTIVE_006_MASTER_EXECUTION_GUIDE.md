# TRIDENT FIX DIRECTIVE 006
## Master Execution Guide (Single Entry Orchestration Document)

---

## 1. Purpose

Eliminate execution ambiguity by creating a single, authoritative document that defines the exact build path for Trident.

This directive addresses the engineering feedback that the current document set is not fully actionable due to fragmentation and lack of a single entry point.

---

## 2. Problem

Engineering currently must interpret:

- 000A–000O (architecture)
- 100A–100N (implementation)
- FIX 001–005 (enforcement patches)

This creates:
- cognitive overload
- incorrect build order risk
- inconsistent application of fixes
- potential architecture drift

---

## 3. Required Fix

Engineering must create:

👉 TRIDENT_MASTER_EXECUTION_GUIDE_v1_0.md

This document becomes the ONLY entry point for implementation.

---

## 4. Required Structure

The document MUST include:

### 4.1 System Overview (1–2 pages max)
- High-level architecture summary
- Component relationships
- No deep theory

---

### 4.2 Canonical Build Order

Must explicitly define:

```text
START HERE

Phase 1 (canonical detail — prefer **Master Execution Guide v1.1** for **100O** / **100U** ordering):
100A → 100B → 100C → 100O → 100D → 100E → 100F → 100G → 100H → 100I → 100J → 100U

Phase 2 (IDE):
100K → 100L → 100M → 100N
```

---

### 4.3 Inline Dependencies

Each step must include:

- Required prior directives (no cross-search required)
- Required system state

Example:

```text
100E — Git + File Lock

Requires:
- Schema (100B)
- LangGraph state (100C)

Depends on:
- Directive 000E
```

---

### 4.4 Fix Directive Injection Points

The guide must explicitly state WHERE fixes apply:

Example:

```text
Before 100M:
Apply FIX 001 (IDE Write Gate)
Apply FIX 003 (Lock Heartbeat)
```

---

### 4.5 Execution Rules

Define:

- No skipping phases
- No parallel implementation of dependent systems
- No feature work outside LangGraph/MCP/Lock boundaries

---

### 4.6 Anti-Drift Rules

Must include:

- Backend is source of truth
- No IDE bypass
- No direct execution
- No direct file edits
- No memory writes outside graph

---

### 4.7 Completion Criteria per Phase

Each phase must define:

- What “done” means
- What proof is required
- What blocks next phase

---

## 5. Hard Constraints

Engineering must NOT:

- create new directives inside this document
- duplicate logic from existing directives
- rewrite architecture
- introduce new behavior

This is an orchestration document ONLY.

---

## 6. Acceptance Criteria

This directive is complete only if:

- A single master execution guide exists
- Build order is explicit
- Fixes are correctly injected
- No cross-document hunting is required
- Engineering can follow the build without interpretation

---

## 7. Required Tests

Engineering must validate:

- A new engineer can start from this document alone
- No missing dependencies are encountered
- No ambiguity in next step exists at any point

---

## 8. Proof Objects Required

Engineering must return:

- master guide document
- example walkthrough of following it
- validation notes from test reader
- confirmation of no ambiguity

---

## 9. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000A–000O, 100A–100N, FIX 001–005  
Blocks: ALL IMPLEMENTATION UNTIL COMPLETE

---

END OF DOCUMENT
