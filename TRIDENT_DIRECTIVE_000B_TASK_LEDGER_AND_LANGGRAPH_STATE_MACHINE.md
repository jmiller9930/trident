# Project Trident — Directive 000B

```yaml
manifest_id: TRIDENT-MANIFEST-v1.0
project: Project Trident
parent_document: TRIDENT_DOCUMENT_MANIFEST_v1_0.md
document_id: TRIDENT-DIRECTIVE-000B
document_type: LLD Directive
sequence: 000B
status: Issued
dependencies:
  - TRIDENT-FOUNDATION-v1.0
  - TRIDENT-DIRECTIVE-000A
produces:
  - Task ledger source-of-truth model
  - LangGraph runtime state machine contract
  - Ownership and concurrency rules
  - Acknowledgment enforcement rules
  - Rejection and retry mechanics
  - Failure state model
langgraph_required: true
```

## Title
Task Ledger and LangGraph State Machine Runtime Enforcement

## Version
v1.0

## Owner
Chief Architect

## Purpose
This directive defines the runtime source of truth for Project Trident. Directive 000A defined schemas and graph contracts. Directive 000B defines how those schemas become a living system through a persistent task ledger and enforced LangGraph state machine.

This document does not authorize feature implementation, UI construction, MCP execution, model routing, or autonomous code mutation. It authorizes engineering to design the state model that all later implementation must obey.

---

# 1. Core Rule

The task ledger is the authoritative blackboard for all active and historical work.

LangGraph is the only valid runtime mechanism for changing task lifecycle state, transferring ownership, recording acknowledgments, routing proof objects, and closing directives.

No agent, API endpoint, UI action, worker, or execution adapter may directly bypass the task ledger or mutate lifecycle state outside a governed LangGraph transition.

---

# 2. Runtime Architecture Position

Directive 000B sits directly beneath Directive 000A.

```text
Directive Schema and Graph Contracts (000A)
        ↓
Task Ledger and LangGraph Runtime State Machine (000B)
        ↓
Memory System / Blackboard Retrieval (000C)
        ↓
Agent Contracts (000D)
        ↓
Git, File Locks, MCP, Router, UI Bindings
```

The ledger is not merely a log. It is the operating memory of the workflow.

---

# 3. Task Ledger Definition

The task ledger records every directive, graph instance, lifecycle state, handoff, acknowledgment, proof object, ownership assignment, lock relationship, review decision, failure, retry, and closure event.

The task ledger must support both:

1. Current-state reads for UI and agents.
2. Append-only event history for audit and recovery.

The ledger must therefore have two logical surfaces:

```text
current_task_state
append_only_task_events
```

The current state answers:

- What is happening now?
- Who owns it?
- Which graph node is active?
- What is blocked?
- What proof exists?
- What is waiting for acknowledgment?

The append-only event stream answers:

- What happened?
- Who did it?
- When did it happen?
- What changed?
- What proof was attached?
- What rejection or approval occurred?

---

# 4. Required Task Ledger Entity

Every directive must have a task ledger record.

Required fields:

```json
{
  "task_id": "TRIDENT-TASK-000B-001",
  "directive_id": "TRIDENT-DIRECTIVE-000B",
  "graph_id": "trident_default_delivery_graph_v1",
  "graph_instance_id": "graph-run-uuid",
  "project_id": "project-uuid",
  "workspace_id": "workspace-uuid",
  "current_state": "DRAFT",
  "active_node": "architect",
  "active_owner_agent": "architect_agent",
  "active_owner_user": "user-or-null",
  "requires_ack": false,
  "blocked": false,
  "block_reason": null,
  "proof_status": "NOT_REQUIRED_YET",
  "git_status": "NOT_EVALUATED",
  "lock_status": "NO_LOCKS",
  "created_at": "iso8601",
  "updated_at": "iso8601",
  "closed_at": null
}
```

Implementation may normalize this into multiple tables or collections, but the logical contract must remain intact.

---

# 5. Canonical Lifecycle States

Trident task lifecycle states are mandatory.

```text
DRAFT
APPROVED
QUEUED
IN_PROGRESS
WAITING_FOR_ACK
WAITING_FOR_APPROVAL
WAITING_FOR_PROOF
READY_FOR_REVIEW
REVIEW_IN_PROGRESS
REJECTED
REVISION_REQUIRED
READY_FOR_DOCUMENTATION
DOCUMENTATION_IN_PROGRESS
READY_FOR_CLOSURE
CLOSED
FAILED
CANCELLED
```

No implementation may invent unapproved lifecycle states without updating the manifest and this directive.

---

# 6. LangGraph Node Model

The default Trident graph must include these logical nodes:

```text
operator_intake
architect_define_directive
architect_acceptance_criteria
engineering_acknowledge
engineering_plan
engineering_implementation
engineering_proof_collection
reviewer_acknowledge
reviewer_validation
reviewer_decision
documentation_acknowledge
documentation_update
closure_review
closed
rejected_to_engineering
failed
cancelled
```

Agents are not free-floating actors. Agent roles execute as graph nodes.

A node may call tools, retrieve context, request memory, or request execution, but it must return control to the graph state machine.

---

# 7. Valid Transition Rules

The following transitions are required in the default delivery graph.

```text
DRAFT → APPROVED
APPROVED → QUEUED
QUEUED → IN_PROGRESS
IN_PROGRESS → WAITING_FOR_ACK
WAITING_FOR_ACK → IN_PROGRESS
IN_PROGRESS → WAITING_FOR_APPROVAL
WAITING_FOR_APPROVAL → IN_PROGRESS
IN_PROGRESS → WAITING_FOR_PROOF
WAITING_FOR_PROOF → READY_FOR_REVIEW
READY_FOR_REVIEW → REVIEW_IN_PROGRESS
REVIEW_IN_PROGRESS → REJECTED
REVIEW_IN_PROGRESS → READY_FOR_DOCUMENTATION
REJECTED → REVISION_REQUIRED
REVISION_REQUIRED → IN_PROGRESS
READY_FOR_DOCUMENTATION → DOCUMENTATION_IN_PROGRESS
DOCUMENTATION_IN_PROGRESS → READY_FOR_CLOSURE
READY_FOR_CLOSURE → CLOSED
ANY_NON_CLOSED_STATE → FAILED
ANY_NON_CLOSED_STATE → CANCELLED
```

Transition guards are mandatory.

Examples:

- A task cannot move to `READY_FOR_REVIEW` without required proof objects.
- A task cannot move to `CLOSED` without reviewer acceptance and documentation status.
- A task cannot move from handoff to active work without acknowledgment.
- A task cannot execute mutation work if required file locks are not granted.
- A task cannot mutate repository files if Git governance has not approved the working state.

---

# 8. Acknowledgment Chain

Every handoff between agents must produce an acknowledgment event before the receiving agent performs work.

Required acknowledgment fields:

```json
{
  "ack_id": "ack-uuid",
  "task_id": "TRIDENT-TASK-000B-001",
  "handoff_id": "handoff-uuid",
  "from_agent": "architect_agent",
  "to_agent": "engineer_agent",
  "acknowledged_by": "engineer_agent",
  "acknowledged_at": "iso8601",
  "understood_inputs": true,
  "missing_inputs": [],
  "ack_status": "ACKNOWLEDGED"
}
```

If the receiving agent detects missing inputs, the acknowledgment must be negative:

```json
{
  "ack_status": "REJECTED_FOR_MISSING_INPUTS",
  "missing_inputs": ["acceptance_criteria", "required_proof"]
}
```

A negative acknowledgment must route back to the prior responsible node.

---

# 9. Ownership and Concurrency

Only one active owner may control a task at a time.

A task may have observers, reviewers, and users with visibility, but only one active owner may mutate the task state.

Ownership fields must include:

```json
{
  "active_owner_type": "agent",
  "active_owner_id": "engineer_agent",
  "owning_node": "engineering_implementation",
  "ownership_started_at": "iso8601",
  "ownership_expires_at": null,
  "ownership_status": "ACTIVE"
}
```

Concurrency requirements:

- A second agent cannot act while another owns the active node.
- A UI user cannot override ownership without producing an override event.
- Stale ownership recovery must be explicit and audited.
- File locks must reference task ownership.

---

# 10. Rejection Loop Mechanics

Reviewer rejection must never be vague.

A rejection must include:

```json
{
  "review_decision": "REJECTED",
  "failure_reasons": [
    {
      "category": "missing_proof",
      "detail": "No integration test output attached."
    }
  ],
  "required_corrections": [
    "Attach integration test output",
    "Update documentation handoff section"
  ],
  "return_to_node": "engineering_plan"
}
```

When a task is rejected:

1. Existing proof objects remain in history.
2. Superseded proof objects must be marked superseded if new proof is required.
3. The task state moves to `REVISION_REQUIRED`.
4. The graph routes back to the proper engineering node.
5. The Engineer must acknowledge the rejection before resuming.

---

# 11. Proof State Model

Proof is not a comment. Proof is a first-class ledger object.

Proof status values:

```text
NOT_REQUIRED_YET
REQUIRED
PARTIAL
SUBMITTED
UNDER_REVIEW
ACCEPTED
REJECTED
SUPERSEDED
```

A task may not close unless all required proof objects are accepted.

Minimum proof categories supported by the ledger:

```text
git_diff
test_output
execution_log
lint_output
build_output
documentation_update
commit_hash
runtime_health_check
review_note
screenshot_or_ui_evidence
```

---

# 12. Failure Handling

Failures must be explicit and recoverable.

Failure categories:

```text
NODE_EXECUTION_FAILURE
TOOL_FAILURE
MCP_EXECUTION_FAILURE
MEMORY_READ_FAILURE
MEMORY_WRITE_FAILURE
GIT_GOVERNANCE_FAILURE
FILE_LOCK_FAILURE
ACKNOWLEDGMENT_FAILURE
PROOF_VALIDATION_FAILURE
MODEL_ROUTING_FAILURE
USER_CANCELLED
```

Failure event required fields:

```json
{
  "failure_id": "failure-uuid",
  "task_id": "TRIDENT-TASK-000B-001",
  "graph_instance_id": "graph-run-uuid",
  "node": "engineering_proof_collection",
  "failure_category": "PROOF_VALIDATION_FAILURE",
  "failure_detail": "Required test output was not attached.",
  "recoverable": true,
  "recommended_next_state": "REVISION_REQUIRED",
  "created_at": "iso8601"
}
```

No silent failure is allowed.

---

# 13. Event History Requirements

Every state change must append an event.

Minimum event fields:

```json
{
  "event_id": "event-uuid",
  "task_id": "TRIDENT-TASK-000B-001",
  "event_type": "STATE_TRANSITION",
  "from_state": "IN_PROGRESS",
  "to_state": "WAITING_FOR_PROOF",
  "actor_type": "graph_node",
  "actor_id": "engineering_proof_collection",
  "graph_id": "trident_default_delivery_graph_v1",
  "graph_instance_id": "graph-run-uuid",
  "timestamp": "iso8601",
  "payload": {}
}
```

The append-only event history must never be edited in place. Corrections must be represented by new events.

---

# 14. UI Binding Requirements

The UI must read task state from the ledger and graph state, not inferred local UI state.

The UI must display:

- current lifecycle state
- active LangGraph node
- active owner
- pending acknowledgment
- pending approval
- proof status
- rejection reasons
- file locks
- Git status
- execution queue state
- closure eligibility

The UI must not show a task as complete unless the ledger state is `CLOSED`.

---

# 15. Authorization Boundaries

Directive 000B authorizes engineering to design and implement the ledger/state machine model only after explicit engineering handoff.

Directive 000B does not authorize:

- final UI implementation
- MCP command execution
- real file mutation
- Git commit automation
- model router implementation
- autonomous agent execution outside the graph
- production deployment

---

# 16. Acceptance Criteria

Directive 000B is accepted when the architecture provides:

1. A task ledger source-of-truth model.
2. An append-only event history model.
3. Canonical lifecycle states.
4. LangGraph node and transition mapping.
5. Acknowledgment enforcement rules.
6. Ownership and concurrency rules.
7. Rejection loop behavior.
8. Proof state handling.
9. Failure event handling.
10. UI state binding requirements.
11. Clear prohibition against bypassing LangGraph.

---

# 17. Required Proof for Engineering Closure

When implemented later, engineering must provide:

1. Schema files or migrations.
2. Unit tests for valid and invalid transitions.
3. Unit tests proving acknowledgment is required before work resumes.
4. Unit tests proving closure fails without accepted proof.
5. Unit tests proving rejection routes back to engineering.
6. Event history samples.
7. A running graph instance sample.
8. Documentation linking implementation back to this directive and manifest.

---

# 18. Next Document

The next document is:

**TRIDENT-DIRECTIVE-000C — Memory System and Blackboard Architecture**

Do not issue memory implementation work until 000C is complete and linked to the manifest.
