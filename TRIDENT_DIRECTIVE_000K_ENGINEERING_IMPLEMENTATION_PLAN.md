# TRIDENT DIRECTIVE 000K
## Engineering Implementation Plan + Build Sequencing

---

## 1. Purpose

Define the implementation sequence for Trident after completion of the foundation directive set 000A through 000J.

This document does not authorize code implementation by itself. It defines the ordered engineering plan that future implementation directives must follow.

---

## 2. Scope

Covers:

- Build phases
- Dependency order
- Engineering work packages
- Required proof per phase
- Non-skippable implementation gates
- Relationship to the manifest and directive chain

---

## 3. Core Principle

> Engineering must implement Trident in dependency order. No component may be built in isolation if it depends on an unfinished enforcement layer.

The system must be implemented from the control spine outward:

```text
Schemas → Ledger → Memory → Agents → Git/Locks → MCP → Router → UI → Deployment
```

---

## 4. Required Pre-Code Condition

Before engineering writes code, the following documents must exist and be approved:

- Trident Foundation v1.1
- Trident Document Manifest v1.0 or later
- Directive 000A — Schemas + Graph Contracts
- Directive 000B — Task Ledger + LangGraph State Machine
- Directive 000C — Memory System
- Directive 000D — Agent Contracts
- Directive 000E — Git + File Lock Enforcement
- Directive 000F — MCP Execution Layer
- Directive 000G — Local-First Router Policy
- Directive 000H — UI Binding + LangGraph State Visualization
- Directive 000I — System Integration + End-to-End Validation
- Directive 000J — Deployment + Runtime Architecture

---

## 5. Build Phase 1 — Repository + Runtime Skeleton

### Objective

Create the project skeleton, container runtime, configuration structure, and service boundaries.

### Required Output

- Repository structure
- Docker Compose skeleton
- FastAPI backend skeleton
- Web frontend skeleton
- Worker service skeleton
- Database service
- Vector service
- Execution service placeholder

### Required Proof

- Containers start
- Health endpoint responds
- Version endpoint responds
- Logs are written
- No business logic implemented yet

### Gate

Cannot proceed until runtime skeleton is reproducible.

---

## 6. Build Phase 2 — Schema + Persistence Foundation

### Objective

Implement directive, handoff, proof object, graph, task ledger, audit, and lock schemas.

### Depends On

- 000A
- 000B

### Required Output

- Database migrations
- Pydantic or equivalent schema models
- Validation logic
- API read/write stubs
- Test fixtures

### Required Proof

- Schema validation tests pass
- Invalid objects are rejected
- Ledger records persist across restart

### Gate

Cannot proceed until schemas are enforced and persistence is proven.

---

## 7. Build Phase 3 — LangGraph Workflow Spine

### Objective

Implement the mandatory LangGraph workflow engine.

### Depends On

- 000A
- 000B
- 000D

### Required Output

- Default Trident graph
- Architect node
- Engineer node
- Reviewer node
- Documentation node
- Closure node
- Rejection loop
- State persistence

### Required Proof

- Test directive runs through graph
- Agent cannot act outside graph
- State transitions are ledger-backed
- Rejection loop works

### Gate

No agent feature may proceed unless graph enforcement is proven.

---

## 8. Build Phase 4 — Shared Memory System

### Objective

Implement the shared long-term memory system.

### Depends On

- 000C
- LangGraph workflow spine

### Required Output

- Structured memory store
- Vector memory store
- Memory write API
- Memory read API
- Task-scoped retrieval
- Agent-scoped memory views
- Memory audit events

### Required Proof

- Memory persists across restart
- Multiple agents can read shared memory
- Memory writes occur only inside graph nodes
- Retrieval returns scoped relevant records

### Gate

Cannot proceed to router or UI until memory access is stable.

---

## 9. Build Phase 5 — Git + File Lock Enforcement

### Objective

Implement Git governance and file lock management.

### Depends On

- 000E
- Task ledger
- LangGraph state

### Required Output

- Repo validation
- Branch status detection
- Dirty tree detection
- File lock acquisition
- File lock release
- Conflict rejection
- Diff capture

### Required Proof

- Locked files cannot be modified by another agent
- Git status is captured before and after mutation
- Dirty state is visible
- Diff proof object can be produced

### Gate

No file mutation feature may proceed until lock enforcement is proven.

---

## 10. Build Phase 6 — MCP Execution Broker

### Objective

Implement governed execution through MCP.

### Depends On

- 000F
- LangGraph state
- Approval rules

### Required Output

- MCP request schema
- Command classifier
- Approval gate
- Local execution adapter
- SSH adapter placeholder
- Execution receipt store
- Error object model

### Required Proof

- No command executes outside MCP
- Low/medium/high risk classification works
- Approval gate blocks high-risk execution
- Execution receipts are written to memory and ledger

### Gate

No SSH or infrastructure execution may proceed until approval and receipt handling are proven.

---

## 11. Build Phase 7 — Local-First Router

### Objective

Implement local-first routing and external reasoning escalation.

### Depends On

- 000G
- Memory system
- LangGraph node execution

### Required Output

- Router policy engine
- Local model adapter
- External model adapter
- Escalation decision logger
- Token conservation preprocessor
- Routing visibility API

### Required Proof

- Local model is default
- External call is not silent
- Escalation reason is logged
- Prompt payload is reduced before external call
- Router runs inside LangGraph node

### Gate

No production external API usage until routing logs and token minimization are proven.

---

## 12. Build Phase 8 — Web UI Control Plane

### Objective

Implement the browser-based user interface.

### Depends On

- 000H
- Ledger API
- Memory API
- Git/lock API
- Router API
- MCP API

### Required Output

- Left navigation sidebar
- Center directive/chat workspace
- Right truth/control panel
- LangGraph visualization
- Memory inspector
- Git status panel
- File lock panel
- Execution approval panel
- Router decision panel

### Required Proof

- UI reflects backend state
- No mock state accepted
- LangGraph node state visible
- File locks visible
- Approval actions update backend state

### Gate

No UI acceptance unless state is backend-bound and traceable.

---

## 13. Build Phase 9 — Integration + End-to-End Proof

### Objective

Prove the full Trident lifecycle works from directive creation to closure.

### Depends On

- 000I
- All prior phases

### Required Output

- End-to-end test directive
- Agent handoff chain
- Memory writes
- Git/file lock events
- MCP execution receipt
- Router decision log
- Reviewer approval/rejection path
- Documentation update
- Closure proof

### Required Proof

- Full lifecycle test passes
- Failure injection test passes
- Rejection loop test passes
- Audit trail complete
- No untracked state mutation

### Gate

No beta use until end-to-end proof passes.

---

## 14. Build Phase 10 — Deployment Hardening

### Objective

Make the system reproducible, recoverable, and deployable for local and LAN operation.

### Depends On

- 000J
- Full system integration

### Required Output

- Production Docker Compose
- Environment template
- Health checks
- Backup script
- Restore script
- Logging configuration
- Upgrade procedure
- Security checklist

### Required Proof

- Clean install succeeds
- Restart persistence succeeds
- Backup/restore succeeds
- Health checks pass
- LAN mode works with auth enabled

### Gate

No team use until deployment hardening is proven.

---

## 15. Implementation Discipline

Engineering must not:

- Build UI before backend state exists
- Build agents outside LangGraph
- Build memory writes outside graph nodes
- Build execution outside MCP
- Build file mutation outside Git/file lock governance
- Build external routing before local-first policy exists
- Use mock state as proof
- Close tasks without required proof objects

---

## 16. Required Engineering Return Format

Each implementation phase must return:

```text
Phase ID:
Commit Hash:
Files Changed:
Tests Run:
Proof Objects:
Known Gaps:
Next Recommended Phase:
```

---

## 17. Acceptance Criteria

This document is accepted when:

- Build order is clear
- Dependencies are explicit
- No implementation shortcut remains ambiguous
- Every phase has required proof
- Engineering can plan the build without redesigning architecture

---

## 18. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000A–000J  
Unlocks: Phase-specific engineering implementation directives

---

END OF DOCUMENT
