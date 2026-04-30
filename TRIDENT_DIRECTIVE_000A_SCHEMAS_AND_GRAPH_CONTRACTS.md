# Project Trident — Directive 000A

## Title
Directive, Handoff, Proof, Memory, and LangGraph Schema Foundation

## Version
v1.0

## Status
Architecture / LLD Foundation Directive

## Owner
Chief Architect

## Purpose
This directive defines the first low-level design foundation for Project Trident. It converts the locked high-level architecture into explicit schemas and contracts that engineering must implement before writing feature behavior.

This directive does not authorize general application coding yet. It defines the required data structures, graph contracts, lifecycle states, memory records, handoff records, proof objects, and enforcement rules that all later implementation work must follow.

---

# 1. Core Rule

Trident is a memory-first, multi-agent software delivery control plane.

All meaningful project work must flow through LangGraph.

No agent may perform project work outside a governed LangGraph workflow.

This includes:

- directive creation
- task lifecycle transitions
- memory reads
- memory writes
- agent handoffs
- acknowledgments
- file lock requests
- proof routing
- review decisions
- documentation updates
- closure decisions

LangChain may be used for tools, retrieval, prompts, loaders, and model adapters. LangGraph is mandatory for workflow enforcement.

---

# 2. Required Protocol Stack

Trident must implement the following internal protocol stack:

```text
Wire-style Directive Specification
        ↓
ACP-style Agent Handoff Message
        ↓
LangGraph Workflow State Machine
        ↓
Shared Memory / Blackboard
        ↓
MCP Execution Layer
        ↓
Git / Filesystem / SSH / vCenter / External APIs
```

The system must remain compatible with future external standards where practical, but Trident must not wait on external protocol maturity before implementing its own internal contracts.

---

# 3. Directive Schema

Every unit of work in Trident must be represented by a directive.

A directive is not a casual prompt. It is an executable specification.

## Required Directive Fields

```json
{
  "directive_id": "TRIDENT-000A",
  "title": "Define schema foundation",
  "version": "1.0",
  "status": "draft | approved | in_progress | review | rejected | closed",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "created_by": "user_or_agent_id",
  "owning_workspace_id": "workspace_id",
  "project_id": "project_id",
  "graph_id": "langgraph_workflow_id",
  "current_graph_node": "architect | engineer | reviewer | docs | closure",
  "objective": "clear human-readable objective",
  "scope": {
    "included": [],
    "excluded": []
  },
  "acceptance_criteria": [],
  "required_proof_objects": [],
  "allowed_project_roots": [],
  "target_files": [],
  "risk_level": "low | medium | high | critical",
  "requires_human_approval": true,
  "memory_policy": {
    "read_required": true,
    "write_required": true,
    "memory_scopes": []
  },
  "git_policy": {
    "repo_required": true,
    "clean_tree_required_before_start": true,
    "diff_required_before_review": true,
    "commit_required_before_close": true,
    "remote_sync_check_required": true
  },
  "closure_policy": {
    "review_required": true,
    "docs_required": true,
    "proof_required": true,
    "architect_final_acceptance_required": true
  }
}
```

## Directive Rules

A directive cannot enter `approved` unless:

- objective is populated
- graph_id is assigned
- acceptance criteria are present
- proof requirements are present
- memory policy is declared
- Git policy is declared
- closure policy is declared

A directive cannot enter `in_progress` unless:

- LangGraph has started the workflow
- the active node is known
- the assigned agent has acknowledged the prior state
- project memory has been read
- Git state has been checked

A directive cannot enter `closed` unless:

- required proof objects are attached
- reviewer has accepted the work
- documentation requirement is satisfied
- Git policy is satisfied
- final closure node approves the directive

---

# 4. LangGraph Contract

Every directive must bind to a LangGraph workflow.

## Required Default Graph

```text
architect_node
    ↓
engineer_node
    ↓
reviewer_node
    ↓
docs_node
    ↓
closure_node
```

## Required Rejection Loop

```text
reviewer_node → engineer_node
closure_node → engineer_node
closure_node → docs_node
```

## Required Graph State Fields

```json
{
  "directive_id": "TRIDENT-000A",
  "graph_id": "trident_default_delivery_graph_v1",
  "current_node": "architect_node",
  "previous_node": null,
  "next_node": "engineer_node",
  "node_history": [],
  "task_state": "draft",
  "active_agent_id": "agent_architect_default",
  "active_user_id": "user_id_or_null",
  "acknowledgment_required": true,
  "acknowledgment_status": "pending | acknowledged | rejected",
  "memory_snapshot_ids": [],
  "handoff_record_ids": [],
  "proof_object_ids": [],
  "file_lock_ids": [],
  "git_state_id": "git_state_record_id",
  "execution_request_ids": [],
  "review_findings": [],
  "closure_decision": "pending | accepted | rejected"
}
```

## LangGraph Enforcement Rules

- Agents are graph nodes.
- Lifecycle transitions are graph edges.
- Handoffs are graph state events.
- Acknowledgments are graph state events.
- Proof objects attach to graph state.
- Memory reads and writes must be traceable to graph node execution.
- Closure must be performed by a closure node.
- Any agent action outside graph state is invalid and must be logged as a policy violation.

---

# 5. Agent Contracts

## Architect Agent

Responsibilities:

- define directive
- define scope
- define acceptance criteria
- define proof requirements
- select or confirm graph_id
- approve transition to engineering

Required outputs:

- directive record
- acceptance criteria
- proof requirements
- architect handoff record

May not:

- silently skip proof requirements
- close its own directive without review proof
- allow engineering to proceed without graph binding

## Engineer Agent

Responsibilities:

- acknowledge architect handoff
- read memory
- inspect Git state
- request file locks
- propose or make changes through governed file tools
- request MCP execution when needed
- produce proof objects
- hand off to reviewer

Required outputs:

- implementation summary
- changed file list
- Git diff reference
- test output reference
- execution receipt references
- engineer handoff record

May not:

- mutate files outside allowed roots
- bypass file locks
- bypass Git policy
- bypass MCP for execution
- self-approve closure

## Reviewer Agent

Responsibilities:

- acknowledge engineer handoff
- inspect diff
- inspect proof objects
- validate acceptance criteria
- validate Git state
- accept or reject

Required outputs:

- review decision
- review findings
- acceptance or rejection reason
- reviewer handoff record

May not:

- approve without proof
- ignore missing documentation requirements
- ignore Git violations

## Documentation Agent

Responsibilities:

- acknowledge reviewer handoff
- update documentation records
- update memory summaries
- ensure handoff clarity
- prepare closure summary

Required outputs:

- documentation update reference
- memory update reference
- docs handoff record

May not:

- modify code unless explicitly routed back through engineering
- close directive without closure approval

## Closure Node / Architect Final Review

Responsibilities:

- verify all prior nodes completed
- verify all proof requirements satisfied
- verify docs complete
- verify Git clean/committed as required
- close or reject directive

Required outputs:

- closure decision
- closure summary
- final proof manifest

May not:

- close with pending proof
- close with unresolved rejection findings
- close without full lifecycle trace

---

# 6. ACP-Style Handoff Schema

Every transition between agents must create a handoff record.

## Required Handoff Fields

```json
{
  "handoff_id": "handoff_uuid",
  "directive_id": "TRIDENT-000A",
  "graph_id": "trident_default_delivery_graph_v1",
  "from_node": "architect_node",
  "to_node": "engineer_node",
  "from_agent_id": "agent_architect_default",
  "to_agent_id": "agent_engineer_default",
  "created_at": "ISO-8601 timestamp",
  "summary": "human-readable handoff summary",
  "required_actions": [],
  "context_refs": [],
  "memory_snapshot_refs": [],
  "artifact_refs": [],
  "proof_object_refs": [],
  "risk_notes": [],
  "requires_acknowledgment": true,
  "acknowledgment": {
    "status": "pending | acknowledged | rejected",
    "acknowledged_by": null,
    "acknowledged_at": null,
    "acknowledgment_notes": null
  }
}
```

## Handoff Rules

- No receiving agent may act before acknowledgment.
- Rejected acknowledgment must route back to sender or architect node.
- Handoff must include enough context for the next agent to continue without asking for hidden state.
- Handoff must reference memory snapshots instead of relying on unstored chat context.

---

# 7. Proof Object Schema

Every claim of completion must be backed by proof objects.

## Required Proof Fields

```json
{
  "proof_id": "proof_uuid",
  "directive_id": "TRIDENT-000A",
  "graph_id": "trident_default_delivery_graph_v1",
  "created_at": "ISO-8601 timestamp",
  "created_by_agent_id": "agent_engineer_default",
  "proof_type": "git_diff | test_result | execution_log | documentation_update | screenshot | api_response | commit | review_report",
  "title": "human-readable proof title",
  "summary": "what this proof demonstrates",
  "artifact_uri": "path_or_object_store_uri",
  "hash": "sha256_if_available",
  "validated": false,
  "validated_by": null,
  "validated_at": null,
  "validation_notes": null
}
```

## Required Proof Types by Default

Every implementation directive must include:

- Git diff proof
- test or validation proof
- execution log proof where commands were run
- documentation proof if docs were changed or required
- commit proof before closure when commit policy is active

## Proof Rules

- Proof must be attached before review.
- Reviewer must validate proof before acceptance.
- Closure node must verify proof manifest before closing directive.
- Missing proof blocks closure.

---

# 8. Memory Record Schema

Trident memory must be structured and durable.

## Required Memory Record Fields

```json
{
  "memory_id": "memory_uuid",
  "created_at": "ISO-8601 timestamp",
  "updated_at": "ISO-8601 timestamp",
  "workspace_id": "workspace_id",
  "project_id": "project_id",
  "directive_id": "TRIDENT-000A_or_null",
  "graph_id": "langgraph_workflow_id_or_null",
  "source_node": "architect_node | engineer_node | reviewer_node | docs_node | closure_node | system",
  "memory_scope": "system | project | directive | agent | user",
  "memory_type": "architecture_rule | decision | rejection | proof_summary | coding_standard | known_bug | project_fact | handoff_summary",
  "title": "short title",
  "content": "memory content",
  "tags": [],
  "source_refs": [],
  "validity": {
    "status": "active | superseded | disputed | deprecated",
    "superseded_by": null
  },
  "visibility": {
    "roles_allowed": [],
    "agents_allowed": []
  }
}
```

## Memory Rules

- Memory must be scoped.
- Memory must be auditable.
- Memory writes must be tied to graph node execution.
- Project memory is shared across agents.
- Agent-specific working memory cannot override project memory without explicit promotion.
- Rejected ideas must be stored when they materially affect future work.
- The UI must expose relevant memory used by an agent.

---

# 9. Git State Schema

Every directive touching files must capture Git state.

```json
{
  "git_state_id": "git_state_uuid",
  "directive_id": "TRIDENT-000A",
  "project_id": "project_id",
  "repo_root": "absolute_allowed_path",
  "branch": "branch_name",
  "commit_sha_before": "sha",
  "commit_sha_after": "sha_or_null",
  "remote_name": "origin",
  "remote_status": "current | ahead | behind | diverged | unknown",
  "working_tree_status": "clean | dirty",
  "untracked_files": [],
  "modified_files": [],
  "staged_files": [],
  "diff_artifact_ref": null,
  "commit_required": true,
  "commit_ref": null
}
```

## Git Rules

- Repo validation must occur before file mutation.
- Dirty state must be visible before work begins.
- Diff must be captured before review.
- Commit proof is required before closure when policy requires it.
- Remote sync status must be checked before closure.

---

# 10. File Lock Schema

```json
{
  "file_lock_id": "lock_uuid",
  "directive_id": "TRIDENT-000A",
  "project_id": "project_id",
  "file_path": "absolute_allowed_path",
  "locked_by_agent_id": "agent_engineer_default",
  "locked_by_user_id": "user_id_or_null",
  "locked_at": "ISO-8601 timestamp",
  "expires_at": "ISO-8601 timestamp_or_null",
  "status": "active | released | expired | force_released",
  "release_reason": null
}
```

## File Lock Rules

- File locks are required before mutation.
- Lock state must be visible in UI.
- A locked file cannot be edited by another agent or user without policy override.
- Overrides must be audited.

---

# 11. MCP Execution Request Schema

```json
{
  "execution_request_id": "exec_uuid",
  "directive_id": "TRIDENT-000A",
  "graph_id": "trident_default_delivery_graph_v1",
  "requested_by_agent_id": "agent_engineer_default",
  "created_at": "ISO-8601 timestamp",
  "target_type": "local_container | ssh_host | vcenter | external_api",
  "target_id": "target_identifier",
  "command_or_action": "command_or_structured_action",
  "risk_level": "low | medium | high | critical",
  "requires_approval": true,
  "approval_status": "pending | approved | rejected | expired",
  "approved_by": null,
  "approved_at": null,
  "execution_status": "not_started | running | succeeded | failed | canceled",
  "stdout_ref": null,
  "stderr_ref": null,
  "exit_code": null,
  "receipt_ref": null
}
```

## MCP Rules

- No shell, SSH, vCenter, Docker, or external side-effect action may bypass MCP.
- Risk classification is required before approval.
- Approval is required for medium/high/critical actions by default.
- Execution receipts become proof objects when relevant.

---

# 12. UI State Binding Requirements

The UI must reflect backend truth.

The right-side control panel must be bound to:

- LangGraph current node
- task lifecycle state
- active agent
- file locks
- Git state
- proof object manifest
- memory snapshots
- execution queue
- approval state

The UI must never invent comforting state.

If the graph state is blocked, the UI must show blocked.

If proof is missing, the UI must show closure blocked.

If an agent has not acknowledged handoff, the UI must show waiting for acknowledgment.

---

# 13. Directive 000A Acceptance Criteria

Engineering may mark Directive 000A complete only when the following are delivered as design artifacts:

1. Final schema definitions for:
   - Directive
   - Graph state
   - Handoff
   - Proof object
   - Memory record
   - Git state
   - File lock
   - MCP execution request

2. Validation rules for every schema.

3. A default LangGraph workflow definition.

4. A state transition matrix.

5. A lifecycle diagram showing normal and rejection loops.

6. UI state binding contract.

7. Written confirmation that no agent action may bypass LangGraph.

No application feature code should be accepted as completion proof for this directive. This directive is complete when the foundation contracts are defined, reviewed, and approved.

---

# 14. Required Engineering Response

Engineering must respond with:

- summary of implemented design artifacts
- list of files created or modified
- schema validation approach
- LangGraph enforcement explanation
- open questions or risks
- proof artifacts showing the design files exist

Engineering must not begin Directive 000B until Directive 000A is reviewed and accepted.

---

# 15. Closure Statement

Directive 000A establishes the foundation that prevents Trident from becoming a generic chat UI or uncontrolled coding assistant.

The purpose of this directive is to ensure that memory, division of labor, proof, Git governance, MCP execution, and LangGraph enforcement are part of the system foundation before feature implementation begins.
