# Project Trident Foundation v1.0

**Document Type:** Architecture Foundation / Directive 000A  
**Project:** Trident  
**Status:** Draft for architecture lock  
**Purpose:** Define the foundational architecture before engineering implementation begins.

---

## 1. Executive Lock Statement

Project Trident is a memory-first, multi-agent, local-first AI software delivery control plane.

Trident is not merely a chat UI, not merely a local LLM router, and not merely an SSH assistant. Its core purpose is to coordinate specialized agents through shared project memory, executable specifications, structured handoffs, proof objects, and governed execution.

The foundation of Trident is:

> Wire-style executable specifications + ACP-style handoff messaging + LangGraph workflow enforcement + shared blackboard memory + MCP-governed execution + Git-enforced delivery.

---

## 2. High-Level Design Foundation

### 2.1 Product Identity

Trident provides a Cursor-like coding and project assistance experience, but with a stronger architecture:

- local-first LLM usage
- shared project memory
- role-based agent collaboration
- proof-gated task closure
- Git-enforced development rules
- MCP-controlled execution
- team-aware collaboration
- web UI and IDE-compatible API access

Trident must allow users to:

- select approved local or network project folders
- paste large context
- upload documents
- ask questions about a project
- launch structured work directives
- have agents divide work by role
- review diffs and proof objects
- approve or reject execution and commits

### 2.2 Core Differentiator

The central differentiator is not only local inference. The central differentiator is coordinated agent work over shared memory.

Agents must not behave like isolated chats. Every meaningful agent action must read project/task memory, act within its assigned role, write a durable handoff, and expose proof for the next actor.

---

## 3. Required Frameworks and Protocol Stack

### 3.1 LangChain Requirement

LangChain is mandatory for:

- model abstraction
- prompt templates
- tool wrappers
- retrieval chains
- document loaders
- structured output parsing
- external API adapter paths

All project scaffolds created by Trident must include LangChain-compatible structure unless explicitly marked as external/read-only.

### 3.2 LangGraph Requirement

LangGraph is mandatory for:

- stateful multi-agent workflows
- role-based task transitions
- review/reject/repair loops
- persistent workflow state
- deterministic task routing between agents

All major Trident workflows must be expressible as LangGraph state machines.

### 3.3 MCP Requirement

MCP is mandatory for execution and tool access.

All tool use must pass through a governed MCP-compatible abstraction, including:

- filesystem mutation
- SSH execution
- Git commands
- Docker commands
- vCenter or lab API actions
- test execution
- deployment steps

No LLM or agent may directly execute shell commands outside the MCP/governance layer.

### 3.4 Wire-Style Specification Requirement

Trident adopts Wire Framework principles internally:

- work is encoded as executable specifications
- directives define roles, acceptance criteria, gates, and required proof
- tasks are documentable, reviewable, and repeatable
- methodology is explicit instead of hidden in prompts

### 3.5 ACP-Style Handoff Requirement

Trident adopts ACP-style messaging internally:

- agents communicate through structured handoff records
- every handoff requires an acknowledgment from the receiving agent
- the handoff record becomes part of durable project memory
- no agent may proceed without reading and acknowledging the current task state

### 3.6 A2A Compatibility

Trident does not need to implement external A2A protocol in v1, but it must keep its internal handoff model compatible with future agent-to-agent interoperability.

---

## 4. Agent Roles

### 4.1 Architect Agent

Responsible for:

- defining directives
- defining scope boundaries
- defining acceptance criteria
- defining required proof
- approving workflow closure when required

The Architect Agent does not directly implement code unless explicitly assigned.

### 4.2 Engineer Agent

Responsible for:

- implementing code changes
- producing diffs
- running assigned validation through MCP
- generating proof artifacts
- responding to reviewer rejection

The Engineer Agent may not close its own task without review.

### 4.3 Reviewer Agent

Responsible for:

- reviewing code diffs
- checking acceptance criteria
- checking test output
- checking proof objects
- verifying documentation updates
- accepting or rejecting work

The Reviewer Agent must provide explicit rejection reasons when rejecting work.

### 4.4 Documentation Agent

Responsible for:

- updating HLD/LLD documents
- updating README or runbooks
- updating handoff summaries
- ensuring architecture decisions are captured
- ensuring memory records are clear enough for future agents

### 4.5 Operator / Human Owner

Responsible for:

- approving destructive execution
- approving external API spending policies
- approving commits if configured
- overriding locks or failed workflows when necessary

---

## 5. Core Workflow

### 5.1 Standard Directive Lifecycle

```text
Draft
  -> Approved
  -> Assigned
  -> In Progress
  -> Ready For Review
  -> Review Accepted | Review Rejected
  -> Documentation Check
  -> Final Approval
  -> Closed
```

If rejected:

```text
Review Rejected -> Engineer Rework -> Ready For Review
```

### 5.2 Mandatory Handoff Chain

Every role transition requires:

1. sending agent writes handoff
2. receiving agent reads handoff
3. receiving agent acknowledges handoff
4. task ledger records acknowledgment
5. receiving agent may begin work

No silent transition is allowed.

---

## 6. Shared Memory Model

### 6.1 Memory Types

Trident must maintain the following memory layers:

#### Session Memory
Short-term conversation/task context.

#### Project Memory
Persistent memory scoped to a project, including:

- architecture rules
- coding patterns
- prior accepted decisions
- rejected approaches
- known bugs
- test commands
- deployment procedures
- project-specific instructions

#### Task Memory
Directive-specific context, including:

- current owner
- current state
- required proof
- pending blockers
- handoff history
- review history

#### System Memory / RLM
Structured lab and infrastructure topology, including:

- hosts
- services
- vCenter targets
- network boundaries
- allowed execution targets
- tool capabilities

#### Vector Memory
Embeddings over approved files, uploaded documents, code, logs, and relevant project artifacts.

### 6.2 Blackboard Rule

All agents coordinate through the shared memory system. This is the Trident blackboard.

Agents may have scoped views, but they may not operate without first loading relevant task/project memory.

---

## 7. Directive Specification Schema

A Trident directive must be represented as both Markdown and JSON.

### 7.1 Directive Markdown Sections

Required sections:

- Title
- Context
- Goal
- Scope
- Out of Scope
- Assigned Roles
- Required Inputs
- Required Outputs
- Acceptance Criteria
- Required Proof Objects
- Handoff Rules
- Git Rules
- Documentation Rules
- Closure Rules

### 7.2 Directive JSON Schema v1

```json
{
  "schema_version": "trident_directive_v1",
  "directive_id": "TRIDENT-000A",
  "title": "Define Trident Foundation",
  "status": "draft",
  "project_id": "trident",
  "created_by": "operator",
  "roles": {
    "architect": "required",
    "engineer": "required",
    "reviewer": "required",
    "documentation": "required"
  },
  "scope": [],
  "out_of_scope": [],
  "acceptance_criteria": [],
  "required_proof_objects": [],
  "workflow": {
    "engine": "langgraph",
    "states": [],
    "transitions": []
  },
  "git_policy": {
    "repo_required": true,
    "dirty_tree_allowed": false,
    "commit_required_for_closure": true,
    "remote_sync_required": true
  },
  "execution_policy": {
    "mcp_required": true,
    "destructive_actions_require_human_approval": true
  }
}
```

---

## 8. Agent Handoff Schema

### 8.1 Handoff Record v1

```json
{
  "schema_version": "trident_handoff_v1",
  "handoff_id": "H-000001",
  "directive_id": "TRIDENT-000A",
  "from_agent": "architect",
  "to_agent": "engineer",
  "from_role": "architect",
  "to_role": "engineer",
  "state_before": "approved",
  "state_after": "assigned",
  "summary": "Directive approved for implementation planning.",
  "instructions": [],
  "required_artifacts": [],
  "known_risks": [],
  "blocking_issues": [],
  "requires_ack": true,
  "created_at": "ISO-8601 timestamp",
  "acknowledged_at": null,
  "acknowledged_by": null
}
```

### 8.2 Acknowledgment Rule

Before beginning work, the receiving agent must write:

```json
{
  "schema_version": "trident_ack_v1",
  "handoff_id": "H-000001",
  "directive_id": "TRIDENT-000A",
  "acknowledged_by": "engineer",
  "understood_scope": true,
  "understood_acceptance_criteria": true,
  "understood_required_proof": true,
  "questions_or_blockers": [],
  "acknowledged_at": "ISO-8601 timestamp"
}
```

---

## 9. Proof Object Schema

### 9.1 Proof Object v1

```json
{
  "schema_version": "trident_proof_object_v1",
  "proof_id": "P-000001",
  "directive_id": "TRIDENT-000A",
  "produced_by": "engineer",
  "proof_type": "test_output",
  "title": "Unit test results",
  "artifact_path": "runtime/proofs/TRIDENT-000A/unit_tests.log",
  "summary": "All unit tests passed.",
  "result": "pass",
  "created_at": "ISO-8601 timestamp",
  "verified_by": null,
  "verified_at": null
}
```

### 9.2 Required Proof Types

Common proof types:

- git_status
- git_diff
- test_output
- lint_output
- runtime_log
- command_receipt
- documentation_diff
- commit_hash
- remote_sync_check
- reviewer_decision

No directive may close without its declared proof objects.

---

## 10. Git Governance Foundation

Every writable project must be a Git repository.

Mandatory rules:

- detect repo root before edits
- detect branch before edits
- detect dirty tree before edits
- create or require task branch if configured
- produce diff after edits
- run validation before closure
- commit before closure if policy requires
- verify remote sync if policy requires

No agent may silently mutate files outside this governance model.

---

## 11. File Locking Foundation

Trident must enforce file-level locking.

A file lock must include:

```json
{
  "schema_version": "trident_file_lock_v1",
  "lock_id": "L-000001",
  "project_id": "trident",
  "directive_id": "TRIDENT-000A",
  "file_path": "relative/path/to/file.py",
  "locked_by": "engineer",
  "lock_reason": "implementation",
  "created_at": "ISO-8601 timestamp",
  "expires_at": "ISO-8601 timestamp or null",
  "status": "active"
}
```

No two agents may write the same file concurrently.

---

## 12. Execution Governance Foundation

All execution must produce receipts.

### 12.1 Command Receipt v1

```json
{
  "schema_version": "trident_command_receipt_v1",
  "receipt_id": "C-000001",
  "directive_id": "TRIDENT-000A",
  "requested_by": "engineer",
  "approved_by": "operator_or_policy",
  "execution_target": "local_container_or_ssh_host",
  "command_classification": "safe_read_only",
  "command": "pytest tests/",
  "started_at": "ISO-8601 timestamp",
  "finished_at": "ISO-8601 timestamp",
  "exit_code": 0,
  "stdout_path": "runtime/proofs/TRIDENT-000A/stdout.log",
  "stderr_path": "runtime/proofs/TRIDENT-000A/stderr.log",
  "result": "pass"
}
```

### 12.2 Execution Classes

- safe_read_only
- safe_validation
- file_mutation
- package_install
- service_restart
- destructive
- infrastructure_change

Destructive and infrastructure_change actions require human approval.

---

## 13. Container Foundation

Trident should run as a containerized web application and API control plane.

Baseline services:

```text
trident-web
trident-api
trident-worker
trident-db
trident-vector
trident-exec
```

The local model runtime may run as:

- host Ollama / MLX / llama.cpp
- containerized Ollama
- external model API adapter

---

## 14. Project Scaffold Requirement

Any new project launched through Trident must include a default agentic scaffold unless disabled by policy.

Required scaffold:

```text
agents/
chains/
graphs/
memory/
prompts/
tools/
tests/
docs/
langgraph.json
requirements.txt
README.md
```

This ensures that LangChain and LangGraph are part of every Trident-created project foundation.

---

## 15. Low-Level Directive Breakdown

The HLD is now locked around memory-first multi-agent orchestration.

The LLD breaks into the following directive bodies of work:

### Directive 000A — Foundation Schema Lock
Define directive schema, handoff schema, proof object schema, task ledger states, and closure rules.

### Directive 000B — Memory Architecture Lock
Define project memory, task memory, vector memory, system topology memory, access rules, and retention rules.

### Directive 000C — LangGraph Workflow Lock
Define Architect -> Engineer -> Reviewer -> Documentation -> Closure state graph, rejection loops, and ownership rules.

### Directive 000D — MCP Execution Lock
Define command classification, approval rules, command receipts, SSH targets, and tool adapters.

### Directive 000E — Git and File Lock Lock
Define Git enforcement, branch rules, file locks, diff requirements, commit rules, and rollback rules.

### Directive 000F — UI/UX Lock
Define web UI behavior: chat, project selector, document upload, task board, agent handoff view, proof view, execution approval, and Git state display.

### Directive 000G — IDE/API Compatibility Lock
Define OpenAI-compatible endpoint behavior for Cursor, Continue, VS Code, and future Code-OSS fork compatibility.

### Directive 001 — Implementation Skeleton
Only after 000A through 000G are accepted may engineering begin the implementation skeleton.

---

## 16. Acceptance Criteria for This Foundation

This foundation is accepted only if the operator agrees that:

- memory is the core application layer
- agents coordinate through shared memory
- no agent works in isolation
- LangChain and LangGraph are mandatory
- MCP governs execution
- Wire-style specifications define work
- ACP-style handoffs define agent communication
- Git and file locks are mandatory
- proof objects are mandatory for closure
- code implementation does not begin until directive bodies are locked

---

## 17. Immediate Next Action

Engineering must not begin product code yet.

The next required artifact is:

**Directive 000A — Foundation Schema Lock**

That directive must formalize the exact schemas for:

- directive records
- task ledger records
- handoff records
- acknowledgment records
- proof objects
- command receipts
- file locks
- review decisions

