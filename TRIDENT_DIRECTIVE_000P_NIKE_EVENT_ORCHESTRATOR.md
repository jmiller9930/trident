# TRIDENT DIRECTIVE 000P
## Nike Event Orchestrator (Non-Intelligent Background Coordination Service)

---

## 1. Purpose

Define **Nike**, Trident's internal event orchestration service.

Nike exists to keep the Trident system coordinated across the API, UI, IDE, LangGraph workflows, memory, file locks, MCP execution requests, router events, and background jobs.

Nike is not an agent, not an LLM, and not a decision-maker.

---

## 2. Core Identity

> Nike is a non-intelligent orchestration service responsible for event routing, workflow triggering, background coordination, retries, and system notifications.

Nike coordinates the system.

Nike does not reason.

Nike does not write code.

Nike does not execute commands.

Nike does not bypass LangGraph.

---

## 3. Placement in Architecture

Nike sits between the API/event producers and the workflow/runtime consumers.

### 3.1 Backend authority and client boundary

The **Trident backend** is the **work-processing authority**. **IDE** and **web** clients are frontends; they **produce** events and user actions to the **API** but **do not** host product agent execution. **Agent-oriented work** flows **server-side**:

```text
IDE / Web → Trident API → Nike → LangGraph → Agents / Memory / Router / MCP / Proof
```

**Nike** is **not** an LLM and **not** an agent; it **routes** and **coordinates** so that **LangGraph** and approved services remain authoritative. This chain must remain stable as **backend-managed agent role** behavior expands.

### 3.2 Diagram (Nike in the stack)

```text
IDE / Web UI
      ↓
Trident API
      ↓
Nike Event Orchestrator
      ↓
LangGraph Workflow Engine
      ↓
Agents / Memory / Router / MCP / Proof / Git-Lock Services
```

(Aligned with §3.1 canonical chain; Git/Lock governs mutation paths.)

### 3.3 Future agent role hooks (extensibility)

Nike’s **event model and routing** must be designed so these **backend-managed** agent **roles** (and graph nodes or handler bindings) can be added **without redesign** of the API→Nike→LangGraph spine:

- Engineer agent  
- Reviewer agent  
- Documentation agent  
- Debugger agent  
- Test agent  
- Security review agent  
- Performance review agent  
- Deployment/release agent  

Concretely: new work is expressed as **event types**, **payloads**, and **LangGraph** transitions **or** server-side handler registration — **not** as new IDE-only execution engines.

Nike may also receive events from:

```text
Memory Indexer
MCP Execution Broker
Router
Git/Lock Service
Worker Jobs
UI/IDE Sessions
```

---

## 4. Responsibilities

Nike is responsible for:

### 4.1 Workflow Triggering

- Directive created → trigger Architect node
- Architect complete → signal Engineer readiness
- Engineer complete → signal Reviewer readiness
- Reviewer rejects → route back to Engineer through LangGraph
- Reviewer approves → signal Documentation node
- Documentation complete → signal Closure node

---

### 4.2 Event Routing

Nike routes system events to the correct subsystem.

Examples:

```text
DIRECTIVE_CREATED → LangGraph workflow start
NODE_COMPLETED → next graph node evaluation
MCP_APPROVAL_PENDING → UI/IDE notification
LOCK_STALE → lock recovery workflow
MEMORY_INDEX_COMPLETE → memory status update
ROUTER_ESCALATION_REQUIRED → router audit + UI notification
```

---

### 4.3 Notification Coordination

Nike notifies:

- Web UI
- IDE client
- active user sessions
- task owners
- agent state panels
- approval panels

Notifications must reflect real backend state only.

---

### 4.4 Background Job Coordination

Nike may coordinate:

- memory indexing jobs
- stale lock scans
- retry scheduling
- failed workflow recovery
- audit event dispatch
- proof artifact collection
- UI/IDE state refresh signals

---

### 4.5 Retry and Recovery

Nike must support controlled retry behavior for:

- transient worker failures
- stale lock detection
- delayed memory indexing
- MCP execution result collection
- UI notification delivery

Retries must be bounded, logged, and policy-controlled.

---

## 5. Non-Responsibilities

Nike must NOT:

- act as an agent
- call LLMs directly
- make architecture decisions
- choose model routing
- execute shell commands
- mutate files
- apply patches
- approve MCP actions
- bypass file locks
- bypass Git governance
- bypass LangGraph state transitions
- write memory outside approved service APIs
- close directives

---

## 6. Event Model

Nike consumes and emits structured events.

Minimum event envelope:

```json
{
  "event_id": "uuid",
  "event_type": "DIRECTIVE_CREATED",
  "source": "trident-api",
  "workspace_id": "uuid",
  "project_id": "uuid",
  "directive_id": "uuid",
  "task_id": "uuid",
  "correlation_id": "uuid",
  "payload": {},
  "created_at": "iso8601"
}
```

---

## 7. Required Event Types

Nike must support at least:

```text
DIRECTIVE_CREATED
DIRECTIVE_UPDATED
GRAPH_NODE_READY
GRAPH_NODE_STARTED
GRAPH_NODE_COMPLETED
GRAPH_NODE_FAILED
HANDOFF_CREATED
HANDOFF_ACKNOWLEDGED
PROOF_ATTACHED
MCP_APPROVAL_PENDING
MCP_EXECUTION_COMPLETED
MCP_EXECUTION_FAILED
LOCK_CREATED
LOCK_STALE
LOCK_RELEASED
MEMORY_WRITE_COMMITTED
MEMORY_VECTOR_INDEX_PENDING
MEMORY_VECTOR_INDEXED
ROUTER_DECISION_LOGGED
ROUTER_ESCALATION_REQUIRED
UI_NOTIFICATION_REQUIRED
IDE_NOTIFICATION_REQUIRED
SYSTEM_ERROR
```

---

## 8. LangGraph Boundary

Nike may trigger or wake LangGraph workflows.

Nike may not decide workflow outcomes.

Rules:

- LangGraph remains the workflow authority.
- Graph state remains authoritative.
- Nike only dispatches events and triggers graph evaluation.
- Any transition must still be recorded through graph state and task ledger.
- Nike cannot skip graph nodes or force closure.

---

## 9. Memory Boundary

Nike may observe memory events and schedule indexing.

Nike may not directly mutate memory content outside approved memory service APIs.

Rules:

- structured memory remains authoritative
- vector indexing is coordinated, not decided, by Nike
- stale memory states must be surfaced
- memory write ordering remains governed by Directive 000C and Fix Directive 004

---

## 10. MCP Boundary

Nike may notify users that MCP approval is pending.

Nike may not approve or execute MCP actions.

Rules:

- MCP remains the execution boundary
- user approval rules still apply
- Nike may retry notification delivery
- Nike may not transform command intent into execution

---

## 11. Git and Lock Boundary

Nike may watch lock events and trigger stale lock workflows.

Nike may not grant locks by itself unless routed through the lock service.

Rules:

- lock service remains authority
- Git service remains authority
- Nike may schedule lock heartbeat checks
- Nike may emit stale-lock events
- forced unlocks remain policy/audit controlled

---

## 12. Router Boundary

Nike may observe and dispatch router events.

Nike may not choose local vs external model itself.

Rules:

- router service remains authority
- router decisions are logged
- Nike may notify UI/IDE of routing outcomes
- Nike may not initiate external LLM calls directly

---

## 13. Delivery Guarantees

Nike must provide:

- at-least-once delivery for critical events
- idempotency through event_id and correlation_id
- retry limits
- dead-letter handling for failed events
- event audit trail

---

## 14. Storage Requirements

Nike event records must be persisted.

Minimum storage:

```text
events
event_attempts
dead_letter_events
notification_outbox
```

Events must be queryable by:

- directive_id
- task_id
- project_id
- event_type
- correlation_id
- timestamp

---

## 15. UI / IDE Visibility

The UI and IDE must expose Nike-driven status where relevant:

- workflow waiting
- notification pending
- retrying event
- dead-lettered event
- stale lock event
- background indexing pending
- MCP approval pending

No fake status is allowed.

---

## 16. Observability

Nike must log:

- event received
- event dispatched
- event retry
- event failed
- dead-lettered event
- notification delivered
- notification failed

Logs must be structured and tied to correlation_id.

---

## 17. Failure Handling

Nike failure must not corrupt authoritative state.

If Nike is down:

- API may still write authoritative records
- events may queue for later processing
- workflows may pause but must not proceed incorrectly
- UI/IDE must show degraded orchestration state

Recovery must resume pending events safely.

---

## 18. Implementation Placement

Nike should be implemented after the LangGraph workflow spine exists and before full memory/router/UI integration.

Recommended implementation order update:

```text
100A → 100B → 100C → 100O (Nike) → 100D → 100E → 100F → 100G → 100H → 100I → 100J → 100U
```

IDE track remains:

```text
100K → 100P → 100M → 100N
```

Fix directive gates remain unchanged unless explicitly updated.

---

## 19. Required Future Implementation Directive

This architecture directive unlocks:

```text
TRIDENT_IMPLEMENTATION_DIRECTIVE_100O_NIKE_EVENT_ORCHESTRATOR.md
```

100O must implement:

- event tables
- event dispatcher
- retry loop
- dead-letter queue
- notification outbox
- LangGraph wakeup integration
- structured logging
- tests and proof objects

---

## 20. Acceptance Criteria

Directive 000P is accepted when:

- Nike is defined as a non-intelligent orchestration service
- Nike responsibilities and non-responsibilities are explicit
- Nike does not conflict with LangGraph, MCP, memory, router, Git, or lock authority
- Nike event model is defined
- Nike implementation placement is defined
- Future 100O implementation directive is unlocked

---

## 21. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000A–000O, Fix 004, Fix 003  
Updates: 000B, 000C, 000H, 000I, 000J, 000K, 100C, 100D, 100H (Agent), 100U (UI), 100I  
Unlocks: 100O — Nike Event Orchestrator Implementation

---

END OF DOCUMENT
